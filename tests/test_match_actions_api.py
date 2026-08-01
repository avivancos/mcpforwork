"""Match action + profile write API (S6.6b): the dashboard's low-risk writes.

POST /v1/matches/{id}/approve|discard|restore|outcome and POST /v1/profile,
plus the GET /v1/profile shape alignment to the web's `Profile` contract.

Zero mocks: real Starlette TestClient on a real tmp SQLite database.
"""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from mcpforwork.adapters.db import connect
from mcpforwork.entrypoints.api.app import create_app
from mcpforwork.services import apply as apply_service
from mcpforwork.services import hunt, profiles, review

_SECRET = "test-secret-please-rotate"


class _CapturingMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_magic_link(self, email: str, link: str) -> None:
        self.sent.append((email, link))


@pytest.fixture
def env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MCPFORWORK_DB_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("MCPFORWORK_SESSION_SECRET", _SECRET)
    return tmp_path


def _client(mailer: _CapturingMailer) -> TestClient:
    return TestClient(
        create_app(mailer=mailer), base_url="https://testserver", raise_server_exceptions=False
    )


def _login(client: TestClient, mailer: _CapturingMailer, email: str) -> None:
    client.post("/v1/auth/magic-link", json={"email": email})
    token = parse_qs(urlparse(mailer.sent[-1][1]).query)["token"][0]
    assert client.get(f"/v1/auth/redeem?token={token}").status_code == 200


@pytest.fixture
def api(env):
    mailer = _CapturingMailer()
    client = _client(mailer)
    _login(client, mailer, "ada@example.com")
    return client, env


def _uid(env, email="ada@example.com") -> int:
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        return uow.fetchone("SELECT id FROM users WHERE email = ?", (email,))["id"]
    finally:
        uow.close()


def _seed_finding(env, uid: int, url: str, title: str = "Nurse") -> int:
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        hunt.submit_findings(uow, uid, "weworkremotely", [{"url": url, "title": title}])
        fid = uow.fetchone(
            "SELECT id FROM explore_findings WHERE user_id = ? AND url = ?", (uid, url)
        )["id"]
        uow.commit()
        return fid
    finally:
        uow.close()


def _finding_status(env, uid: int, fid: int) -> str:
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        return uow.fetchone(
            "SELECT status FROM explore_findings WHERE user_id = ? AND id = ?", (uid, fid)
        )["status"]
    finally:
        uow.close()


def _submitted_application(env, uid: int, fid: int) -> int:
    """Drive the real services to a submitted application; returns its id."""
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        if profiles.get_profile(uow, uid) is None:
            profiles.create_profile(uow, uid, {"full_name": "Ada Lovelace"})
        review.approve_match(uow, uid, fid)
        app_id = apply_service.start_application(uow, uid, fid)["application_id"]
        uow.execute(
            "UPDATE applications SET state = 'submitted' WHERE id = ? AND user_id = ?",
            (app_id, uid),
        )
        uow.commit()
        return app_id
    finally:
        uow.close()


# --------------------------------------------------------------------------- #
# Auth + tenancy
# --------------------------------------------------------------------------- #
def test_match_actions_require_authentication(env):
    client = _client(_CapturingMailer())
    for method in ("approve", "discard", "restore", "outcome"):
        assert client.post(f"/v1/matches/1/{method}").status_code == 401
    assert client.post("/v1/profile", json={}).status_code == 401


def test_actions_on_unknown_or_foreign_matches_are_404(api):
    client, env = api
    assert client.post("/v1/matches/99999/approve").status_code == 404
    assert client.post("/v1/matches/99999/discard").status_code == 404
    assert client.post("/v1/matches/99999/restore").status_code == 404
    assert client.post("/v1/matches/99999/outcome", json={"outcome": "rejected"}).status_code == 404

    # a foreign finding is indistinguishable from a missing one
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        uow.execute("INSERT INTO users (email) VALUES ('bob@example.com')")
        bob = uow.fetchone("SELECT id FROM users WHERE email = 'bob@example.com'")["id"]
        hunt.submit_findings(
            uow, bob, "weworkremotely", [{"url": "https://b.example/1", "title": "T"}]
        )
        bob_fid = uow.fetchone("SELECT id FROM explore_findings WHERE user_id = ?", (bob,))["id"]
        uow.commit()
    finally:
        uow.close()
    assert client.post(f"/v1/matches/{bob_fid}/approve").status_code == 404


# --------------------------------------------------------------------------- #
# approve / discard / restore
# --------------------------------------------------------------------------- #
def test_approve_moves_a_new_match_to_approved(api):
    client, env = api
    uid = _uid(env)
    fid = _seed_finding(env, uid, "https://example.com/a")
    assert client.post(f"/v1/matches/{fid}/approve").status_code == 204
    assert _finding_status(env, uid, fid) == "approved"


def test_approve_is_status_guarded(api):
    client, env = api
    uid = _uid(env)
    fid = _seed_finding(env, uid, "https://example.com/b")
    assert client.post(f"/v1/matches/{fid}/approve").status_code == 204
    # second approve: 'approved' is not in the approvable set
    assert client.post(f"/v1/matches/{fid}/approve").status_code == 400


def test_discard_records_the_reason(api):
    client, env = api
    uid = _uid(env)
    fid = _seed_finding(env, uid, "https://example.com/c")
    r = client.post(f"/v1/matches/{fid}/discard", json={"reason": "not remote"})
    assert r.status_code == 204
    assert _finding_status(env, uid, fid) == "discarded"
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        row = uow.fetchone(
            "SELECT detail FROM audit_log WHERE user_id = ? AND action = 'discard_match'",
            (uid,),
        )
        assert json.loads(row["detail"])["reason"] == "not remote"
    finally:
        uow.close()


def test_restore_only_reopens_a_discarded_match(api):
    client, env = api
    uid = _uid(env)
    fid = _seed_finding(env, uid, "https://example.com/d")
    # not discarded yet → restore refuses
    assert client.post(f"/v1/matches/{fid}/restore").status_code == 400
    client.post(f"/v1/matches/{fid}/discard")
    assert client.post(f"/v1/matches/{fid}/restore").status_code == 204
    assert _finding_status(env, uid, fid) == "new"


# --------------------------------------------------------------------------- #
# outcome
# --------------------------------------------------------------------------- #
def test_outcome_maps_the_web_vocabulary_to_the_service_vocabulary(api):
    client, env = api
    uid = _uid(env)
    fid = _seed_finding(env, uid, "https://example.com/e")
    app_id = _submitted_application(env, uid, fid)
    r = client.post(f"/v1/matches/{fid}/outcome", json={"outcome": "no_response"})
    assert r.status_code == 204
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        row = uow.fetchone("SELECT outcome FROM applications WHERE id = ?", (app_id,))
        assert row["outcome"] == "no_reply"  # the service vocabulary
    finally:
        uow.close()


def test_outcome_without_an_application_is_a_400(api):
    client, env = api
    uid = _uid(env)
    fid = _seed_finding(env, uid, "https://example.com/f")
    r = client.post(f"/v1/matches/{fid}/outcome", json={"outcome": "rejected"})
    assert r.status_code == 400  # outcomes only apply after submission


def test_outcome_rejects_an_unknown_value(api):
    client, env = api
    uid = _uid(env)
    fid = _seed_finding(env, uid, "https://example.com/g")
    _submitted_application(env, uid, fid)
    assert client.post(f"/v1/matches/{fid}/outcome", json={"outcome": "ghosted"}).status_code == 400


# --------------------------------------------------------------------------- #
# profile GET shape + POST mapping
# --------------------------------------------------------------------------- #
def test_profile_get_returns_the_web_shape_for_a_fresh_user(api):
    client, _ = api
    body = client.get("/v1/profile").json()
    assert body["name"] == ""
    assert body["tier1Step"] == 1  # onboarding starts
    assert body["achievements"] == []
    assert body["styleProfile"] is None


def test_profile_post_maps_web_fields_to_profile_columns(api):
    client, env = api
    uid = _uid(env)
    r = client.post(
        "/v1/profile",
        json={
            "name": "Ada Lovelace",
            "email": "ada@lovelace.dev",
            "headline": "Engineer · 10 yrs",
            "targetRole": "Staff Engineer",
            "seniority": "Senior",
            "employmentType": "Full-time",
            "workMode": "hybrid",
            "languages": "Spanish (native) · English (C1)",
            "cities": ["Dublin", "Cork"],
            # display-only fields: no intake column — ignored by design
            "workRights": "EU citizen",
            "salaryFloor": "€52,000 / year",
            "tier1Step": 3,
        },
    )
    assert r.status_code == 204
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        profile = profiles.get_profile(uow, uid)
        assert profile["full_name"] == "Ada Lovelace"
        assert profile["contact_email"] == "ada@lovelace.dev"
        assert profile["career_narrative"] == "Engineer · 10 yrs"
        assert profile["target_titles"] == ["Staff Engineer"]
        assert profile["seniority"] == "senior"
        assert profile["employment_types"] == ["full_time"]
        assert profile["work_modes"] == ["hybrid"]
        assert profile["languages"] == ["Spanish (native)", "English (C1)"]
        assert profile["city"] == "Dublin"  # first entry; collapse documented
    finally:
        uow.close()


def test_profile_get_round_trips_the_web_shape(api):
    client, env = api
    client.post("/v1/profile", json={"name": "Ada", "workMode": "remote", "cities": ["Dublin"]})
    body = client.get("/v1/profile").json()
    assert body["name"] == "Ada"
    assert body["workMode"] == "remote"
    assert body["cities"] == ["Dublin"]
    assert body["tier1Step"] == 2  # profile exists, tier-1 gaps still open


def test_profile_post_rejects_an_invalid_enum(api):
    client, _ = api
    r = client.post("/v1/profile", json={"seniority": "Supreme Leader"})
    assert r.status_code == 400


def test_profile_post_does_not_create_schema_for_display_fields(api):
    client, env = api
    uid = _uid(env)
    client.post("/v1/profile", json={"salaryFloor": "€52,000 / year", "workRights": "EU"})
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        profile = profiles.get_profile(uow, uid)
        # nothing was persisted for display-only fields (no profile even created
        # when the patch maps to nothing)
        assert profile is None or profile.get("min_salary_amount") is None
    finally:
        uow.close()


# --------------------------------------------------------------------------- #
# S6.10 — structured error kinds (no substring sniffing) + action test gaps
# --------------------------------------------------------------------------- #
def test_review_errors_carry_a_structured_kind(env):
    uid = 1
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        uow.execute("INSERT INTO users (id, email) VALUES (1, 'ada@example.com')")
        hunt.submit_findings(
            uow, 1, "weworkremotely", [{"url": "https://a.example/1", "title": "Nurse"}]
        )
        fid = uow.fetchone("SELECT id FROM explore_findings WHERE user_id = 1")["id"]
        uow.commit()

        assert review.approve_match(uow, uid, 9999)["kind"] == "not_found"
        assert review.discard_match(uow, uid, 9999)["kind"] == "not_found"
        assert review.restore_match(uow, uid, 9999)["kind"] == "not_found"
        # state-guarded actions on an existing match
        assert review.restore_match(uow, uid, fid)["kind"] == "invalid_state"
        review.approve_match(uow, uid, fid)
        assert review.approve_match(uow, uid, fid)["kind"] == "invalid_state"
    finally:
        uow.close()


def test_record_outcome_errors_carry_a_structured_kind(env):
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        uow.execute("INSERT INTO users (id, email) VALUES (1, 'ada@example.com')")
        hunt.submit_findings(
            uow, 1, "weworkremotely", [{"url": "https://a.example/1", "title": "Nurse"}]
        )
        fid = uow.fetchone("SELECT id FROM explore_findings WHERE user_id = 1")["id"]
        profiles.create_profile(uow, 1, {"full_name": "Ada Lovelace"})
        review.approve_match(uow, 1, fid)
        app_id = apply_service.start_application(uow, 1, fid)["application_id"]
        uow.commit()

        bad = apply_service.record_outcome(uow, 1, app_id, "ghosted")
        assert bad["kind"] == "invalid_input"
        missing = apply_service.record_outcome(uow, 1, 9999, "rejected")
        assert missing["kind"] == "not_found"
        # application still in draft — outcomes only apply after submission
        early = apply_service.record_outcome(uow, 1, app_id, "rejected")
        assert early["kind"] == "invalid_state"
    finally:
        uow.close()


def test_outcome_on_a_filling_application_is_a_400(api):
    client, env = api
    uid = _uid(env)
    fid = _seed_finding(env, uid, "https://example.com/filling")
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        if profiles.get_profile(uow, uid) is None:
            profiles.create_profile(uow, uid, {"full_name": "Ada Lovelace"})
        review.approve_match(uow, uid, fid)
        app_id = apply_service.start_application(uow, uid, fid)["application_id"]
        uow.execute(
            "UPDATE applications SET state = 'filling' WHERE id = ? AND user_id = ?",
            (app_id, uid),
        )
        uow.commit()
    finally:
        uow.close()
    r = client.post(f"/v1/matches/{fid}/outcome", json={"outcome": "rejected"})
    assert r.status_code == 400  # invalid transition via the API, not just approve


def test_foreign_match_discard_restore_and_outcome_are_404(api):
    client, env = api
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        uow.execute("INSERT INTO users (email) VALUES ('bob@example.com')")
        bob = uow.fetchone("SELECT id FROM users WHERE email = 'bob@example.com'")["id"]
        hunt.submit_findings(
            uow, bob, "weworkremotely", [{"url": "https://b.example/9", "title": "T"}]
        )
        bob_fid = uow.fetchone("SELECT id FROM explore_findings WHERE user_id = ?", (bob,))["id"]
        uow.commit()
    finally:
        uow.close()
    assert client.post(f"/v1/matches/{bob_fid}/discard").status_code == 404
    assert client.post(f"/v1/matches/{bob_fid}/restore").status_code == 404
    r = client.post(f"/v1/matches/{bob_fid}/outcome", json={"outcome": "rejected"})
    assert r.status_code == 404


def test_restore_writes_an_audit_row(api):
    client, env = api
    uid = _uid(env)
    fid = _seed_finding(env, uid, "https://example.com/restore-audit")
    client.post(f"/v1/matches/{fid}/discard")
    assert client.post(f"/v1/matches/{fid}/restore").status_code == 204
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        row = uow.fetchone(
            "SELECT detail FROM audit_log WHERE user_id = ? AND action = 'restore_match'",
            (uid,),
        )
        assert row is not None
        assert json.loads(row["detail"])["finding_id"] == fid
    finally:
        uow.close()


def test_profile_post_does_not_smuggle_raw_intake_keys(api):
    client, env = api
    uid = _uid(env)
    assert client.post("/v1/profile", json={"name": "Ada"}).status_code == 204
    # raw intake column names in the web body must NOT pass through
    r = client.post(
        "/v1/profile",
        json={"full_name": "Mallory", "label": "x", "min_salary_amount": 999999},
    )
    assert r.status_code == 204
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        profile = profiles.get_profile(uow, uid)
        assert profile["full_name"] == "Ada"  # untouched by the smuggled key
        assert profile.get("min_salary_amount") is None
    finally:
        uow.close()
