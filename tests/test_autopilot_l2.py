"""Autopilot L2 (S7.2b): recorded policy + safe-board queue.

ADR 0005 extended: the POLICY is a consent artifact too — written exclusively
by the human-session HTTP API (PUT/revoke), never by the MCP entrypoint. The
MCP reads policy and queue; `request_submit` evaluates L1 approval first,
then the L2 policy (active AND source auto_apply_safe AND score >= min AND
authorized-today < cap), else await_human. Every L2 authorization writes a
criteria-snapshot audit row and flips consent_level 0 -> 2 atomically.

Zero mocks: real SQLite at tmp_path; safe-source sets and time are injected
via arguments (never patched); API arm via Starlette TestClient.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mcpforwork.adapters.db import connect
from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.entrypoints.api.app import create_app
from mcpforwork.services import apply as apply_service
from mcpforwork.services import autopilot, hunt, profiles, review

_SAFE = frozenset({"weworkremotely"})
_URL = "https://x.com/jobs/l2"


def _policy(uow: SqlUnitOfWork, uid: int, min_score: int = 70, cap: int = 2) -> dict:
    result = autopilot.put_policy(uow, uid, min_score=min_score, max_per_day=cap)
    assert result["ok"] is True
    return result


def _approved_match(
    uow: SqlUnitOfWork, uid: int, url: str, score: int, title: str = "Data Engineer"
) -> int:
    """An approved finding with a deterministic score (seeded, not scored)."""
    hunt.submit_findings(uow, uid, "weworkremotely", [{"url": url, "title": title}])
    # Anchor by URL: list_matches ordering must never pick a prior test finding.
    fid = uow.fetchone("SELECT id FROM explore_findings WHERE url = ? AND user_id = ?", (url, uid))[
        "id"
    ]
    uow.execute("UPDATE explore_findings SET score = ? WHERE id = ?", (score, fid))
    review.approve_match(uow, uid, fid)
    uow.commit()
    return fid


def _ready_app(uow: SqlUnitOfWork, email: str, url: str, score: int = 90) -> tuple[int, int, int]:
    """A filled application at submit_requested on a high-scoring approved match."""
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", (email,))
    profiles.create_profile(uow, uid, {"full_name": "Ada", "target_titles": ["Data Engineer"]})
    fid = _approved_match(uow, uid, url, score)
    session = apply_service.start_application(uow, uid, fid)
    app_id = session["application_id"]
    for step in session["steps"]:
        apply_service.report_apply_progress(uow, uid, app_id, step["step_id"], "ok")
    apply_service.request_submit(uow, uid, app_id, summary="form filled")
    uow.commit()
    return uid, fid, app_id


# --------------------------------------------------------------------------- #
# Policy write/read (service level — the API routes are thin shells over this)
# --------------------------------------------------------------------------- #


def test_put_policy_persists_an_active_policy(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("p@example.com",))
    result = autopilot.put_policy(uow, uid, min_score=80, max_per_day=3)
    uow.commit()
    assert result["ok"] is True
    policy = autopilot.get_policy(uow, uid)
    assert policy is not None
    assert policy["min_score"] == 80
    assert policy["max_per_day"] == 3
    assert policy["enabled"] in (True, 1)
    assert policy["revoked_at"] is None


def test_put_policy_validates_ranges(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("v@example.com",))
    for bad in (-1, 101):
        assert (
            autopilot.put_policy(uow, uid, min_score=bad, max_per_day=2).get("kind")
            == "invalid_input"
        )
    for bad in (0, 51):
        assert (
            autopilot.put_policy(uow, uid, min_score=50, max_per_day=bad).get("kind")
            == "invalid_input"
        )
    assert autopilot.get_policy(uow, uid) is None  # nothing persisted


def test_put_policy_supersedes_the_previous_one_and_keeps_history(
    uow: SqlUnitOfWork,
) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("s@example.com",))
    autopilot.put_policy(uow, uid, min_score=50, max_per_day=1)
    autopilot.put_policy(uow, uid, min_score=90, max_per_day=5)
    uow.commit()
    policy = autopilot.get_policy(uow, uid)
    assert policy["min_score"] == 90 and policy["max_per_day"] == 5
    rows = uow.fetchall(
        "SELECT min_score, revoked_at FROM autopilot_policy WHERE user_id = ? ORDER BY id", (uid,)
    )
    assert len(rows) == 2  # append-only: the superseded row remains as history
    assert rows[0]["revoked_at"] is not None  # ... marked superseded
    assert rows[1]["revoked_at"] is None


def test_revoke_policy_marks_the_active_row(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("r@example.com",))
    _policy(uow, uid)
    result = autopilot.revoke_policy(uow, uid)
    uow.commit()
    assert result["ok"] is True
    assert autopilot.get_policy(uow, uid) is None
    row = uow.fetchone("SELECT revoked_at FROM autopilot_policy WHERE user_id = ?", (uid,))
    assert row["revoked_at"] is not None  # history kept, not deleted


def test_revoke_without_a_policy_is_not_found(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("n@example.com",))
    assert autopilot.revoke_policy(uow, uid).get("kind") == "not_found"


def test_policy_is_tenant_scoped(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("a@example.com",))
    other = uow.insert("INSERT INTO users (email) VALUES (?)", ("b@example.com",))
    _policy(uow, uid)
    uow.commit()
    assert autopilot.get_policy(uow, other) is None
    assert autopilot.revoke_policy(uow, other).get("kind") == "not_found"
    assert autopilot.get_policy(uow, uid) is not None  # untouched


def test_policy_writes_are_audited(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("au@example.com",))
    autopilot.put_policy(uow, uid, min_score=60, max_per_day=2)
    autopilot.revoke_policy(uow, uid)
    uow.commit()
    actions = [
        r["action"]
        for r in uow.fetchall("SELECT action FROM audit_log WHERE user_id = ? ORDER BY id", (uid,))
    ]
    assert "put_autopilot_policy" in actions
    assert "revoke_autopilot_policy" in actions


# --------------------------------------------------------------------------- #
# evaluate — the pure decision helper
# --------------------------------------------------------------------------- #


def _active_policy(uow: SqlUnitOfWork, uid: int, min_score: int = 70, cap: int = 2) -> dict:
    _policy(uow, uid, min_score, cap)
    return autopilot.get_policy(uow, uid)


def test_evaluate_authorizes_only_when_every_criterion_holds(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("e@example.com",))
    policy = _active_policy(uow, uid, min_score=70, cap=2)

    ok = autopilot.evaluate(
        policy=policy,
        score=70,
        source_slug="weworkremotely",
        safe_sources=_SAFE,
        authorized_today=0,
    )
    assert ok["authorize"] is True
    assert ok["snapshot"]["policy_id"] == policy["id"]
    assert ok["snapshot"]["score"] == 70
    assert ok["snapshot"]["source_slug"] == "weworkremotely"

    assert (
        autopilot.evaluate(
            policy=None,
            score=100,
            source_slug="weworkremotely",
            safe_sources=_SAFE,
            authorized_today=0,
        )["authorize"]
        is False
    )
    assert (
        autopilot.evaluate(
            policy=policy, score=100, source_slug="remotive", safe_sources=_SAFE, authorized_today=0
        )["authorize"]
        is False
    )  # source not safe
    assert (
        autopilot.evaluate(
            policy=policy,
            score=69,
            source_slug="weworkremotely",
            safe_sources=_SAFE,
            authorized_today=0,
        )["authorize"]
        is False
    )  # below min
    assert (
        autopilot.evaluate(
            policy=policy,
            score=100,
            source_slug="weworkremotely",
            safe_sources=_SAFE,
            authorized_today=2,
        )["authorize"]
        is False
    )  # cap hit


# --------------------------------------------------------------------------- #
# autopilot_queue — a query, not a table
# --------------------------------------------------------------------------- #


def test_queue_filters_safe_approved_scoring_unblocked_matches(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("q@example.com",))
    profiles.create_profile(uow, uid, {"full_name": "Ada", "target_titles": ["Data Engineer"]})
    _policy(uow, uid, min_score=70)

    keep = _approved_match(uow, uid, "https://x.com/jobs/keep", 85)
    _approved_match(uow, uid, "https://x.com/jobs/low", 40)  # below min
    unsafe = _approved_match(uow, uid, "https://x.com/jobs/unsafe", 95)
    uow.execute("UPDATE explore_findings SET source_slug = 'remotive' WHERE id = ?", (unsafe,))
    discarded = _approved_match(uow, uid, "https://x.com/jobs/disc", 95)
    review.discard_match(uow, uid, discarded)
    with_app = _approved_match(uow, uid, "https://x.com/jobs/open", 95)
    apply_service.start_application(uow, uid, with_app)  # open application
    uow.commit()

    items = autopilot.queue(uow, uid, safe_sources=_SAFE)["items"]
    ids = [i["id"] for i in items]
    assert ids == [str(keep)]

    # Dedup-blocked: an external application with the same hash drops the match.
    fid = _approved_match(uow, uid, "https://x.com/jobs/dup", 99)
    from mcpforwork.services import dedup as dedup_service

    dedup_service.record_application(
        uow, uid, url="https://x.com/jobs/dup", channel="browser_supervised", title="DE"
    )
    uow.commit()
    ids = [i["id"] for i in autopilot.queue(uow, uid, safe_sources=_SAFE)["items"]]
    assert str(fid) not in ids


def test_queue_without_a_policy_is_honestly_empty(uow: SqlUnitOfWork) -> None:
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("np@example.com",))
    result = autopilot.queue(uow, uid, safe_sources=_SAFE)
    assert result["policy"] is None
    assert result["items"] == []


def test_queue_defaults_to_empty_when_no_shipped_pack_is_flagged(uow: SqlUnitOfWork) -> None:
    """The conservative default is pinned: until S7.2c human-verifies a board,
    NO source is auto_apply_safe, so the registry-driven queue is empty even
    with a policy and a perfect approved match."""
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("c@example.com",))
    profiles.create_profile(uow, uid, {"target_titles": ["DE"]})
    _policy(uow, uid, min_score=1)
    _approved_match(uow, uid, "https://x.com/jobs/perfect", 100)
    result = autopilot.queue(uow, uid)  # safe_sources from the real registry
    assert result["items"] == []


# --------------------------------------------------------------------------- #
# request_submit — the L2 branch (decision order: L1 -> L2 -> await_human)
# --------------------------------------------------------------------------- #


def test_request_submit_authorizes_under_an_l2_policy(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow, "l2@example.com", _URL, score=90)
    _policy(uow, uid, min_score=70, cap=2)
    uow.commit()

    result = apply_service.request_submit(uow, uid, app_id, safe_sources=_SAFE)
    uow.commit()
    assert result["decision"] == "submit_authorized"
    row = uow.fetchone("SELECT consent_level FROM applications WHERE id = ?", (app_id,))
    assert row["consent_level"] == 2
    audit_row = uow.fetchone(
        "SELECT detail FROM audit_log WHERE action = 'submit_authorized' AND user_id = ?",
        (uid,),
    )
    detail = json.loads(audit_row["detail"])
    assert detail["level"] == 2
    assert detail["snapshot"]["score"] == 90
    assert detail["snapshot"]["source_slug"] == "weworkremotely"
    assert detail["snapshot"]["cap_used"] == 1
    assert detail["snapshot"]["policy_id"] is not None


def test_l1_approval_wins_over_an_l2_policy(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow, "both@example.com", _URL, score=90)
    _policy(uow, uid, min_score=70, cap=2)
    autopilot.approve_submit(uow, uid, app_id, via="dashboard")
    uow.commit()
    result = apply_service.request_submit(uow, uid, app_id, safe_sources=_SAFE)
    assert result["decision"] == "submit_authorized"
    row = uow.fetchone("SELECT consent_level FROM applications WHERE id = ?", (app_id,))
    assert row["consent_level"] == 1  # L1, not L2


def test_request_submit_refuses_l2_when_source_is_not_safe(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow, "ns@example.com", _URL, score=100)
    _policy(uow, uid, min_score=1, cap=5)
    uow.commit()
    result = apply_service.request_submit(uow, uid, app_id, safe_sources=frozenset())
    assert result["decision"] == "await_human"
    assert (
        uow.fetchone("SELECT consent_level FROM applications WHERE id = ?", (app_id,))[
            "consent_level"
        ]
        == 0
    )


def test_request_submit_refuses_l2_below_min_score(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow, "low@example.com", _URL, score=50)
    _policy(uow, uid, min_score=80, cap=5)
    uow.commit()
    assert (
        apply_service.request_submit(uow, uid, app_id, safe_sources=_SAFE)["decision"]
        == "await_human"
    )


def _fill_and_pause(uow: SqlUnitOfWork, uid: int, fid: int) -> int:
    """A second application walked to submit_requested (the state the gate
    evaluates)."""
    session = apply_service.start_application(uow, uid, fid)
    app_id = session["application_id"]
    for step in session["steps"]:
        apply_service.report_apply_progress(uow, uid, app_id, step["step_id"], "ok")
    apply_service.request_submit(uow, uid, app_id)
    return app_id


def test_request_submit_refuses_l2_when_the_daily_cap_is_hit(uow: SqlUnitOfWork) -> None:
    uid, _, app1 = _ready_app(uow, "cap@example.com", "https://x.com/jobs/c1", score=90)
    _policy(uow, uid, min_score=70, cap=1)
    uow.commit()
    assert (
        apply_service.request_submit(uow, uid, app1, safe_sources=_SAFE)["decision"]
        == "submit_authorized"
    )

    fid2 = _approved_match(uow, uid, "https://x.com/jobs/c2", 95)
    app2 = _fill_and_pause(uow, uid, fid2)
    uow.commit()
    assert (
        apply_service.request_submit(uow, uid, app2, safe_sources=_SAFE)["decision"]
        == "await_human"
    )  # cap=1 already used by app1


def test_utc_cap_window_resets_at_midnight(uow: SqlUnitOfWork) -> None:
    """An authorization written yesterday 23:59 UTC does not count against
    today's cap; one written today 00:00 does. Time is injected, never patched."""
    uid, _, app_id = _ready_app(uow, "utc@example.com", _URL, score=90)
    policy = _active_policy(uow, uid, min_score=70, cap=1)
    uow.execute(
        "INSERT INTO audit_log (user_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
        (
            uid,
            "submit_authorized",
            json.dumps(
                {"application_id": 999, "level": 2, "snapshot": {"policy_id": policy["id"]}}
            ),
            "2026-07-31T23:59:59Z",  # yesterday, UTC
        ),
    )
    uow.commit()
    now = datetime(2026, 8, 1, 0, 0, 1, tzinfo=UTC)
    assert (
        apply_service.request_submit(uow, uid, app_id, now=now, safe_sources=_SAFE)["decision"]
        == "submit_authorized"
    )

    # Same setup, but the prior authorization landed today 00:00:00 UTC.
    uid2, _, app2 = _ready_app(uow, "utc2@example.com", "https://x.com/jobs/u2", score=90)
    policy2 = _active_policy(uow, uid2, min_score=70, cap=1)
    uow.execute(
        "INSERT INTO audit_log (user_id, action, detail, created_at) VALUES (?, ?, ?, ?)",
        (
            uid2,
            "submit_authorized",
            json.dumps(
                {"application_id": 998, "level": 2, "snapshot": {"policy_id": policy2["id"]}}
            ),
            "2026-08-01T00:00:00Z",  # today, UTC
        ),
    )
    uow.commit()
    assert (
        apply_service.request_submit(uow, uid2, app2, now=now, safe_sources=_SAFE)["decision"]
        == "await_human"
    )


def test_revoking_the_policy_mid_batch_stops_new_authorizations(uow: SqlUnitOfWork) -> None:
    uid, _, app1 = _ready_app(uow, "mid@example.com", "https://x.com/jobs/m1", score=90)
    _policy(uow, uid, min_score=70, cap=5)
    uow.commit()
    assert (
        apply_service.request_submit(uow, uid, app1, safe_sources=_SAFE)["decision"]
        == "submit_authorized"
    )

    autopilot.revoke_policy(uow, uid)
    fid2 = _approved_match(uow, uid, "https://x.com/jobs/m2", 95)
    app2 = _fill_and_pause(uow, uid, fid2)
    uow.commit()
    assert (
        apply_service.request_submit(uow, uid, app2, safe_sources=_SAFE)["decision"]
        == "await_human"
    )

    # The already-minted authorization is not recalled: re-entry still authorizes.
    assert (
        apply_service.request_submit(uow, uid, app1, safe_sources=_SAFE)["decision"]
        == "submit_authorized"
    )


def test_double_request_submit_l2_is_exactly_once(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow, "once@example.com", _URL, score=90)
    _policy(uow, uid, min_score=70, cap=3)
    uow.commit()
    assert (
        apply_service.request_submit(uow, uid, app_id, safe_sources=_SAFE)["decision"]
        == "submit_authorized"
    )
    assert (
        apply_service.request_submit(uow, uid, app_id, safe_sources=_SAFE)["decision"]
        == "submit_authorized"
    )  # re-entry re-reads consent_level 2
    count = uow.fetchone(
        "SELECT COUNT(*) AS n FROM audit_log WHERE action = 'submit_authorized' AND user_id = ?",
        (uid,),
    )["n"]
    assert count == 1


def test_confirm_submitted_records_browser_autopilot_l2(uow: SqlUnitOfWork) -> None:
    uid, _, app_id = _ready_app(uow, "chan@example.com", _URL, score=90)
    _policy(uow, uid, min_score=70, cap=2)
    apply_service.request_submit(uow, uid, app_id, safe_sources=_SAFE)
    apply_service.confirm_submitted(uow, uid, app_id, evidence="confirmation banner")
    uow.commit()
    row = uow.fetchone("SELECT channel FROM external_applications WHERE user_id = ?", (uid,))
    assert row["channel"] == "browser_autopilot_l2"


# --------------------------------------------------------------------------- #
# API routes (human-session only — ADR 0005)
# --------------------------------------------------------------------------- #


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db = tmp_path / "api.db"
    monkeypatch.setenv("MCPFORWORK_DB_URL", f"sqlite:///{db}")
    monkeypatch.setenv("MCPFORWORK_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("MCPFORWORK_USER_EMAIL", "api-user@example.com")
    return TestClient(create_app())


def _login(client: TestClient, email: str = "api-user@example.com") -> None:
    assert client.post("/v1/auth/magic-link", json={"email": email}).status_code == 202
    # ConsoleMailer prints the link; the token lives in magic_link_tokens — but
    # the honest path is redeeming through the API. The token is sha256-stored,
    # so mint a session directly via the service instead (same seam the redeem
    # route uses).
    from mcpforwork.adapters.db import connect as _connect
    from mcpforwork.config import db_url
    from mcpforwork.services import auth_session

    uow = _connect(db_url())
    uid = uow.fetchone("SELECT id FROM users WHERE email = ?", (email,))["id"]
    cookie = auth_session.issue_session(
        uow, uid, secret="test-secret", now=datetime.now(UTC), user_agent="test"
    )
    uow.commit()
    uow.close()
    client.cookies.set("mcpforwork_session", cookie)


def test_policy_routes_require_a_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert (
        client.put("/v1/autopilot/policy", json={"min_score": 70, "max_per_day": 2}).status_code
        == 401
    )
    assert client.post("/v1/autopilot/policy/revoke").status_code == 401
    assert client.get("/v1/autopilot/policy").status_code == 401


def test_policy_routes_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client(tmp_path, monkeypatch)
    _login(client)

    off = client.get("/v1/autopilot/policy")
    assert off.status_code == 200 and off.json()["policy"] is None

    assert (
        client.put("/v1/autopilot/policy", json={"min_score": 75, "max_per_day": 3}).status_code
        == 204
    )
    on = client.get("/v1/autopilot/policy").json()["policy"]
    assert on["min_score"] == 75 and on["max_per_day"] == 3 and on["revoked_at"] is None

    assert client.post("/v1/autopilot/policy/revoke").status_code == 204
    assert client.get("/v1/autopilot/policy").json()["policy"] is None
    assert client.post("/v1/autopilot/policy/revoke").status_code == 404  # nothing to revoke


def test_put_policy_route_validates_the_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    _login(client)
    assert (
        client.put("/v1/autopilot/policy", json={"min_score": 101, "max_per_day": 2}).status_code
        == 400
    )
    assert (
        client.put("/v1/autopilot/policy", json={"min_score": 50, "max_per_day": 0}).status_code
        == 400
    )
    assert client.put("/v1/autopilot/policy", json={"max_per_day": 2}).status_code == 400
    assert client.put("/v1/autopilot/policy", data="not json").status_code == 400


def test_put_policy_rejects_json_booleans_as_integers(uow: SqlUnitOfWork) -> None:
    """isinstance(True, int) is True — a JSON `true` must never be stored as
    the integer 1 (on Postgres it would 500 against the INT column)."""
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", ("bool@example.com",))
    assert (
        autopilot.put_policy(uow, uid, min_score=True, max_per_day=2).get("kind") == "invalid_input"
    )
    assert (
        autopilot.put_policy(uow, uid, min_score=50, max_per_day=True).get("kind")
        == "invalid_input"
    )
    assert autopilot.get_policy(uow, uid) is None


def test_policy_routes_never_leak_across_tenants(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    _login(client, "first@example.com")
    client.put("/v1/autopilot/policy", json={"min_score": 70, "max_per_day": 2})

    second = _client(tmp_path, monkeypatch)
    _login(second, "second@example.com")
    assert second.get("/v1/autopilot/policy").json()["policy"] is None
    assert second.post("/v1/autopilot/policy/revoke").status_code == 404


# --------------------------------------------------------------------------- #
# MCP tools are read-only (structural)
# --------------------------------------------------------------------------- #


def test_mcp_entrypoint_never_references_policy_writes() -> None:
    """The agent surface can READ policy/queue but can never mint or revoke a
    policy — the write functions' names must not appear in the MCP entrypoint."""
    source = (
        Path(__file__)
        .parent.parent.joinpath("src/mcpforwork/entrypoints/mcp/server.py")
        .read_text()
    )
    assert "put_policy" not in source
    assert "revoke_policy" not in source
    assert "approve_submit" not in source


def test_mcp_policy_tools_are_read_only_and_honest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"sqlite:///{tmp_path / 'm.db'}"
    monkeypatch.setenv("MCPFORWORK_DB_URL", url)
    monkeypatch.setenv("MCPFORWORK_USER_ID", "1")
    from mcpforwork.entrypoints.mcp import server

    off = json.loads(server.get_autopilot_policy())
    assert off["policy"] is None

    # The first tool call already resolved (and created) the local user 1.
    uow = connect(url)
    autopilot.put_policy(uow, 1, min_score=65, max_per_day=4)
    uow.commit()
    uow.close()

    on = json.loads(server.get_autopilot_policy())
    assert on["policy"]["min_score"] == 65 and on["policy"]["max_per_day"] == 4

    queue = json.loads(server.autopilot_queue())
    assert queue["items"] == []  # no shipped pack is auto_apply_safe yet (S7.2c)
    assert queue["policy"]["min_score"] == 65
