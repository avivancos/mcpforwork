"""Autopilot L1 (S7.2a): dashboard approval → one-time submit_authorized.

ADR 0005: consent artifacts are written exclusively by the human-session HTTP
API, never by the MCP entrypoint. The approval lives on the application row
(`submit_approved_at`/`submit_approved_via`); `request_submit` re-evaluates it
and authorizes exactly once per application (consent_level 0 → 1 flip).

Zero mocks: real SQLite at tmp_path; API arm via Starlette TestClient with a
real magic-link session.
"""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from mcpforwork.adapters.db import connect
from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.entrypoints.api.app import create_app
from mcpforwork.services import apply as apply_service
from mcpforwork.services import autopilot, hunt, profiles, review

_URL = "https://x.com/jobs/l1"


def _ready_app(uow: SqlUnitOfWork, email: str = "u@example.com") -> tuple[int, int, int]:
    """An application that has finished filling and asked to submit:
    state submit_requested, no approval yet."""
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", (email,))
    profiles.create_profile(uow, uid, {"full_name": "Ada", "target_titles": ["Data Engineer"]})
    hunt.submit_findings(uow, uid, "weworkremotely", [{"url": _URL, "title": "Data Engineer"}])
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    review.approve_match(uow, uid, fid)
    session = apply_service.start_application(uow, uid, fid)
    app_id = session["application_id"]
    for step in session["steps"]:
        apply_service.report_apply_progress(uow, uid, app_id, step["step_id"], "ok")
    apply_service.request_submit(uow, uid, app_id, summary="form filled")
    uow.commit()
    return uid, fid, app_id


# --------------------------------------------------------------------------- #
# The approval write (service level — the API route is a thin shell over this)
# --------------------------------------------------------------------------- #


def test_approve_submit_writes_the_approval_artifact(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow)
    result = autopilot.approve_submit(uow, uid, app_id, via="dashboard")
    uow.commit()
    assert result["ok"] is True
    row = uow.fetchone(
        "SELECT submit_approved_at, submit_approved_via FROM applications WHERE id = ?", (app_id,)
    )
    assert row["submit_approved_at"]  # ISO timestamp recorded
    assert row["submit_approved_via"] == "dashboard"
    audit_row = uow.fetchone(
        "SELECT detail FROM audit_log WHERE action = 'approve_submit' AND user_id = ?", (uid,)
    )
    assert str(app_id) in audit_row["detail"]


def test_approve_submit_is_state_guarded(uow: SqlUnitOfWork) -> None:
    # filling: the human has not been shown anything yet — nothing to approve.
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("f@example.com",))
    profiles.create_profile(uow, uid, {"target_titles": ["DE"]})
    hunt.submit_findings(uow, uid, "weworkremotely", [{"url": "https://y.com/l1", "title": "DE"}])
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    review.approve_match(uow, uid, fid)
    filling_id = apply_service.start_application(uow, uid, fid)["application_id"]
    uow.commit()
    result = autopilot.approve_submit(uow, uid, filling_id)
    assert result.get("kind") == "invalid_state"

    # submitted: terminal — approval is meaningless.
    uid2, _, app_id = _ready_app(uow, email="g@example.com")
    apply_service.confirm_submitted(uow, uid2, app_id)
    uow.commit()
    assert autopilot.approve_submit(uow, uid2, app_id).get("kind") == "invalid_state"


def test_approve_submit_never_touches_another_users_application(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow)
    other = uow.insert("INSERT INTO users (email) VALUES (?)", ("other@example.com",))
    result = autopilot.approve_submit(uow, other, app_id)
    assert result.get("kind") == "not_found"
    row = uow.fetchone("SELECT submit_approved_at FROM applications WHERE id = ?", (app_id,))
    assert row["submit_approved_at"] is None  # untouched


def test_double_approve_is_idempotent_and_never_re_mints(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow)
    assert autopilot.approve_submit(uow, uid, app_id, via="dashboard")["ok"] is True
    first_at = uow.fetchone("SELECT submit_approved_at FROM applications WHERE id = ?", (app_id,))[
        "submit_approved_at"
    ]
    again = autopilot.approve_submit(uow, uid, app_id, via="dashboard")
    uow.commit()
    assert again == {"ok": True, "already_approved": True}
    row = uow.fetchone("SELECT submit_approved_at FROM applications WHERE id = ?", (app_id,))
    assert row["submit_approved_at"] == first_at  # untouched by the re-approve
    assert (
        uow.fetchone(
            "SELECT COUNT(*) AS n FROM audit_log WHERE action = 'approve_submit' AND user_id = ?",
            (uid,),
        )["n"]
        == 1
    )


def test_approve_submit_rejects_an_abandoned_application(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow)
    apply_service.abandon_application(uow, uid, app_id, reason="changed my mind")
    uow.commit()
    assert autopilot.approve_submit(uow, uid, app_id).get("kind") == "invalid_state"


# --------------------------------------------------------------------------- #
# request_submit re-evaluation
# --------------------------------------------------------------------------- #


def test_reentry_without_approval_still_awaits_the_human(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow)
    result = apply_service.request_submit(uow, uid, app_id)  # re-entry
    uow.commit()
    assert result["decision"] == "await_human"
    assert "submit_authorized" not in str(result)


def test_l1_approval_authorizes_exactly_once(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow)
    autopilot.approve_submit(uow, uid, app_id, via="dashboard")
    uow.commit()

    first = apply_service.request_submit(uow, uid, app_id)  # re-entry with approval
    uow.commit()
    assert first["decision"] == "submit_authorized"
    row = uow.fetchone("SELECT consent_level FROM applications WHERE id = ?", (app_id,))
    assert row["consent_level"] == 1
    auth_rows = uow.fetchall(
        "SELECT detail FROM audit_log WHERE action = 'submit_authorized' AND user_id = ?", (uid,)
    )
    assert len(auth_rows) == 1
    detail = json.loads(auth_rows[0]["detail"])
    assert detail["application_id"] == app_id
    assert detail["approved_via"] == "dashboard"
    assert detail["approved_at"]  # the recorded approval timestamp, snapshotted

    # Idempotent re-entry (a retried client call must not strand the agent),
    # but the authorization event is never duplicated.
    second = apply_service.request_submit(uow, uid, app_id)
    uow.commit()
    assert second["decision"] == "submit_authorized"
    assert (
        uow.fetchone(
            "SELECT COUNT(*) AS n FROM audit_log"
            " WHERE action = 'submit_authorized' AND user_id = ?",
            (uid,),
        )["n"]
        == 1
    )


def test_approval_before_request_submit_authorizes_on_first_entry(
    uow: SqlUnitOfWork,
) -> None:
    """The dashboard's 'awaiting you' stage covers awaiting_human too: the
    human may approve before the agent asks; the first request_submit then
    authorizes immediately (no race between human and agent)."""
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("h@example.com",))
    profiles.create_profile(uow, uid, {"full_name": "Ada", "target_titles": ["DE"]})
    hunt.submit_findings(uow, uid, "weworkremotely", [{"url": "https://z.com/l1", "title": "DE"}])
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    review.approve_match(uow, uid, fid)
    session = apply_service.start_application(uow, uid, fid)
    app_id = session["application_id"]
    for step in session["steps"]:
        apply_service.report_apply_progress(uow, uid, app_id, step["step_id"], "ok")
    # state is awaiting_human (no request_submit yet) — approvable already.
    assert autopilot.approve_submit(uow, uid, app_id, via="dashboard")["ok"] is True
    result = apply_service.request_submit(uow, uid, app_id)
    uow.commit()
    assert result["decision"] == "submit_authorized"


def test_confirm_submitted_after_l1_records_the_l1_channel(uow: SqlUnitOfWork) -> None:
    uid, fid, app_id = _ready_app(uow)
    autopilot.approve_submit(uow, uid, app_id, via="dashboard")
    apply_service.request_submit(uow, uid, app_id)
    result = apply_service.confirm_submitted(uow, uid, app_id, evidence="auto-submitted")
    uow.commit()
    assert result["state"] == "submitted"
    row = uow.fetchone(
        "SELECT channel FROM external_applications WHERE user_id = ? AND finding_id = ?",
        (uid, fid),
    )
    assert row["channel"] == "browser_autopilot_l1"


def test_l0_confirm_still_records_browser_supervised(uow: SqlUnitOfWork) -> None:
    uid, fid, app_id = _ready_app(uow)  # no approval — plain L0
    apply_service.confirm_submitted(uow, uid, app_id)
    uow.commit()
    row = uow.fetchone(
        "SELECT channel FROM external_applications WHERE user_id = ? AND finding_id = ?",
        (uid, fid),
    )
    assert row["channel"] == "browser_supervised"


# --------------------------------------------------------------------------- #
# The API route (human-session only — ADR 0005)
# --------------------------------------------------------------------------- #

_SECRET = "test-secret-please-rotate"


class _CapturingMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_magic_link(self, email: str, link: str) -> None:
        self.sent.append((email, link))


@pytest.fixture
def api(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MCPFORWORK_DB_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("MCPFORWORK_SESSION_SECRET", _SECRET)
    mailer = _CapturingMailer()
    client = TestClient(
        create_app(mailer=mailer), base_url="https://testserver", raise_server_exceptions=False
    )
    r = client.post("/v1/auth/magic-link", json={"email": "ada@example.com"})
    assert r.status_code == 202
    token = parse_qs(urlparse(mailer.sent[-1][1]).query)["token"][0]
    assert client.get(f"/v1/auth/redeem?token={token}").status_code == 200
    return client, tmp_path


def _api_ready_app(api) -> int:
    """Drive one application to submit_requested through the services, against
    the same SQLite file the API serves; returns the application id."""
    client, tmp_path = api
    uow = connect(f"sqlite:///{tmp_path / 'api.db'}")
    try:
        uid = uow.fetchone("SELECT id FROM users WHERE email = ?", ("ada@example.com",))["id"]
        profiles.create_profile(uow, uid, {"full_name": "Ada", "target_titles": ["DE"]})
        hunt.submit_findings(uow, uid, "weworkremotely", [{"url": _URL, "title": "DE"}])
        fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
        review.approve_match(uow, uid, fid)
        session = apply_service.start_application(uow, uid, fid)
        app_id = session["application_id"]
        for step in session["steps"]:
            apply_service.report_apply_progress(uow, uid, app_id, step["step_id"], "ok")
        apply_service.request_submit(uow, uid, app_id)
        uow.commit()
        return app_id
    finally:
        uow.close()


def test_approve_submit_route_requires_authentication(api) -> None:
    client, _ = api
    client.cookies.clear()
    assert client.post("/v1/applications/1/approve-submit").status_code == 401


def test_approve_submit_route_happy_path_then_agent_authorizes(api) -> None:
    """The full L1 loop: human approves from the dashboard; the agent's next
    request_submit is authorized; confirm closes as submitted."""
    client, tmp_path = api
    app_id = _api_ready_app(api)
    assert client.post(f"/v1/applications/{app_id}/approve-submit").status_code == 204

    uow = connect(f"sqlite:///{tmp_path / 'api.db'}")
    try:
        uid = uow.fetchone("SELECT id FROM users WHERE email = ?", ("ada@example.com",))["id"]
        result = apply_service.request_submit(uow, uid, app_id)
        uow.commit()
        assert result["decision"] == "submit_authorized"
    finally:
        uow.close()


def test_approve_submit_route_is_cross_tenant_blind(api) -> None:
    client, tmp_path = api
    app_id = _api_ready_app(api)
    # A second user with a valid session asks about the first user's app.
    mailer = _CapturingMailer()
    other = TestClient(
        create_app(mailer=mailer), base_url="https://testserver", raise_server_exceptions=False
    )
    other.post("/v1/auth/magic-link", json={"email": "eve@example.com"})
    token = parse_qs(urlparse(mailer.sent[-1][1]).query)["token"][0]
    other.get(f"/v1/auth/redeem?token={token}")
    assert other.post(f"/v1/applications/{app_id}/approve-submit").status_code == 404


def test_approve_submit_route_rejects_the_wrong_state(api) -> None:
    client, tmp_path = api
    uow = connect(f"sqlite:///{tmp_path / 'api.db'}")
    try:
        uid = uow.fetchone("SELECT id FROM users WHERE email = ?", ("ada@example.com",))["id"]
        profiles.create_profile(uow, uid, {"full_name": "Ada", "target_titles": ["DE"]})
        hunt.submit_findings(uow, uid, "weworkremotely", [{"url": _URL, "title": "DE"}])
        fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
        review.approve_match(uow, uid, fid)
        filling_id = apply_service.start_application(uow, uid, fid)["application_id"]
        uow.commit()
    finally:
        uow.close()
    assert client.post(f"/v1/applications/{filling_id}/approve-submit").status_code == 400
