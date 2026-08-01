"""Pipeline read API (S6.6a): /v1/pipeline, /v1/pipeline/stats, /v1/matches/{id}
backed by services/pipeline.py — plus the pipeline_stats MCP tool.

Zero mocks: real Starlette TestClient on a real tmp SQLite database; the
service-level parity arm also runs on live Postgres under `-m live` (the
audit_log table is NOT RLS-forced, so the explicit user_id filter is what
keeps tenants apart — that filter is what the live arm proves).
"""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from mcpforwork.adapters.db import connect
from mcpforwork.entrypoints.api.app import create_app
from mcpforwork.entrypoints.mcp import server
from mcpforwork.services import apply as apply_service
from mcpforwork.services import audit, hunt, profiles, review
from mcpforwork.services.pipeline import derive_stage

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


@pytest.fixture
def api(env):
    mailer = _CapturingMailer()
    client = _client(mailer)
    r = client.post("/v1/auth/magic-link", json={"email": "ada@example.com"})
    assert r.status_code == 202
    token = parse_qs(urlparse(mailer.sent[-1][1]).query)["token"][0]
    assert client.get(f"/v1/auth/redeem?token={token}").status_code == 200
    return client, env


def _uid(env) -> int:
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        return uow.fetchone("SELECT id FROM users WHERE email = ?", ("ada@example.com",))["id"]
    finally:
        uow.close()


def _seed_finding(env, uid: int, url: str, title: str, **fields) -> int:
    """Ingest one finding through the real hunt service; returns its id."""
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        result = hunt.submit_findings(
            uow, uid, "weworkremotely", [{"url": url, "title": title, **fields}]
        )
        assert result["new"] == 1
        row = uow.fetchone(
            "SELECT id FROM explore_findings WHERE user_id = ? AND url = ?", (uid, url)
        )
        uow.commit()
        return row["id"]
    finally:
        uow.close()


def _set_application_state(env, uid: int, finding_id: int, state: str, outcome: str | None = None):
    """Place the application in `state` via a real SQL write (transitions are
    covered by the apply suites; these tests exercise the READ model)."""
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        uow.execute(
            "UPDATE applications SET state = ?, outcome = ? WHERE user_id = ? AND finding_id = ?",
            (state, outcome, uid, finding_id),
        )
        uow.commit()
    finally:
        uow.close()


def _start_application(env, uid: int, finding_id: int) -> int:
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        if profiles.get_profile(uow, uid) is None:
            profiles.create_profile(uow, uid, {"full_name": "Ada Lovelace"})
        review.approve_match(uow, uid, finding_id)
        result = apply_service.start_application(uow, uid, finding_id)
        uow.commit()
        return result["application_id"]
    finally:
        uow.close()


# --------------------------------------------------------------------------- #
# Stage derivation (pure)
# --------------------------------------------------------------------------- #
def test_a_discarded_finding_is_discarded_even_with_an_application():
    assert derive_stage("discarded", {"state": "submitted", "outcome": None}) == "discarded"


def test_a_finding_without_an_application_is_a_new_match():
    assert derive_stage("new", None) == "new_match"
    assert derive_stage("approved", None) == "new_match"


def test_an_open_application_in_progress_is_filling():
    assert derive_stage("approved", {"state": "draft", "outcome": None}) == "filling"
    assert derive_stage("approved", {"state": "filling", "outcome": None}) == "filling"


def test_an_application_paused_for_the_human_is_awaiting_you():
    assert derive_stage("approved", {"state": "awaiting_human", "outcome": None}) == "awaiting_you"
    assert (
        derive_stage("approved", {"state": "submit_requested", "outcome": None}) == "awaiting_you"
    )


def test_a_submitted_application_is_submitted_then_verified():
    assert derive_stage("approved", {"state": "submitted", "outcome": None}) == "submitted"
    assert derive_stage("approved", {"state": "verified", "outcome": None}) == "verified"


def test_outcomes_map_to_the_web_vocabulary():
    assert derive_stage("approved", {"state": "submitted", "outcome": "no_reply"}) == "no_response"
    assert derive_stage("approved", {"state": "submitted", "outcome": "rejected"}) == "rejected"
    assert derive_stage("approved", {"state": "submitted", "outcome": "interview"}) == "interview"
    assert derive_stage("approved", {"state": "verified", "outcome": "offer"}) == "offer"
    assert derive_stage("approved", {"state": "verified", "outcome": "hired"}) == "offer"


def test_an_abandoned_application_leaves_the_match_new():
    assert derive_stage("approved", {"state": "abandoned", "outcome": None}) == "new_match"


# --------------------------------------------------------------------------- #
# API routes
# --------------------------------------------------------------------------- #
def test_pipeline_routes_require_authentication(env):
    client = _client(_CapturingMailer())
    assert client.get("/v1/pipeline").status_code == 401
    assert client.get("/v1/pipeline/stats").status_code == 401
    assert client.get("/v1/matches/1").status_code == 401


def test_pipeline_mirrors_the_web_contract_shape(api):
    client, env = api
    uid = _uid(env)
    fid = _seed_finding(
        env,
        uid,
        "https://example.com/jobs/1",
        "Registered Nurse",
        company_name="Hospital",
        location="Dublin",
    )
    _start_application(env, uid, fid)
    _set_application_state(env, uid, fid, "awaiting_human")

    r = client.get("/v1/pipeline")
    assert r.status_code == 200
    (item,) = r.json()
    assert item["id"] == str(fid)
    assert item["role"] == "Registered Nurse"
    assert item["company"] == "Hospital"
    assert item["city"] == "Dublin"
    assert item["stage"] == "awaiting_you"
    assert item["consent"] == "supervised"
    assert item["needsYou"]  # paused reason present
    assert "T" in item["updated"]  # ISO-8601, web humanizes


def test_a_match_without_an_application_has_no_consent_badge(api):
    client, env = api
    uid = _uid(env)
    _seed_finding(env, uid, "https://example.com/jobs/2", "Data Engineer")
    (item,) = client.get("/v1/pipeline").json()
    assert item["stage"] == "new_match"
    assert item["consent"] is None
    assert "needsYou" not in item or item["needsYou"] is None


def test_pipeline_stats_count_the_derived_stages(api):
    client, env = api
    uid = _uid(env)
    _seed_finding(env, uid, "https://example.com/a", "Nurse A")
    fid_b = _seed_finding(env, uid, "https://example.com/b", "Nurse B")
    fid_c = _seed_finding(env, uid, "https://example.com/c", "Nurse C")
    _start_application(env, uid, fid_b)
    _set_application_state(env, uid, fid_b, "awaiting_human")
    _start_application(env, uid, fid_c)
    _set_application_state(env, uid, fid_c, "verified")

    stats = client.get("/v1/pipeline/stats").json()
    assert stats["newMatches"]["count"] == 1
    assert stats["newMatches"]["foundThisWeek"] == 1
    assert stats["needsYou"]["count"] == 1
    assert stats["submitted"]["count"] == 1
    assert stats["submitted"]["verified"] == 1
    assert stats["responses"]["of"] == 1


def test_match_detail_composes_assets_and_audit(api):
    client, env = api
    uid = _uid(env)
    fid = _seed_finding(
        env, uid, "https://example.com/jobs/9", "ICU Nurse", company_name="Mater", location="Dublin"
    )
    app_id = _start_application(env, uid, fid)

    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        from mcpforwork.services import assets

        assets.submit_asset(uow, uid, fid, "cv", "# CV")
        assets.submit_asset(uow, uid, fid, "cover_letter", "Dear …")
        uow.commit()
    finally:
        uow.close()

    r = client.get(f"/v1/matches/{fid}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["id"] == str(fid)
    assert detail["pack"] == "weworkremotely"
    assert detail["postingUrl"] == "https://example.com/jobs/9"
    assert {a["kind"] for a in detail["assets"]} == {"resume", "cover"}
    assert detail["constraintChecks"]  # derived from the score breakdown
    actions = [e["event"].split(" ")[0] for e in detail["audit"]]
    assert "start_application" in actions
    assert app_id  # application existed


def test_match_detail_is_404_for_unknown_or_foreign_ids(api):
    client, env = api
    assert client.get("/v1/matches/99999").status_code == 404

    # another user's finding is invisible (web's getOrNull maps 404 → null)
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        uow.execute("INSERT INTO users (email) VALUES ('bob@example.com')")
        bob = uow.fetchone("SELECT id FROM users WHERE email = 'bob@example.com'")["id"]
        hunt.submit_findings(
            uow, bob, "weworkremotely", [{"url": "https://x.example/1", "title": "T"}]
        )
        bob_fid = uow.fetchone("SELECT id FROM explore_findings WHERE user_id = ?", (bob,))["id"]
        uow.commit()
    finally:
        uow.close()
    assert client.get(f"/v1/matches/{bob_fid}").status_code == 404


def test_pipeline_never_lists_another_users_matches(api):
    client, env = api
    uid = _uid(env)
    _seed_finding(env, uid, "https://example.com/mine", "My Role")
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        uow.execute("INSERT INTO users (email) VALUES ('bob@example.com')")
        bob = uow.fetchone("SELECT id FROM users WHERE email = 'bob@example.com'")["id"]
        hunt.submit_findings(
            uow, bob, "weworkremotely", [{"url": "https://x.example/b", "title": "Bob Job"}]
        )
        uow.commit()
    finally:
        uow.close()
    items = client.get("/v1/pipeline").json()
    assert [i["role"] for i in items] == ["My Role"]


# --------------------------------------------------------------------------- #
# audit_log is NOT RLS-forced: the explicit user_id filter is the only wall
# --------------------------------------------------------------------------- #
def test_match_detail_audit_never_leaks_another_users_rows(any_uow):
    from mcpforwork.services import pipeline

    uow = any_uow
    uow.execute("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
    uow.execute("INSERT INTO users (id, email) VALUES (2, 'b@example.com')")
    hunt.submit_findings(
        uow, 1, "weworkremotely", [{"url": "https://a.example/1", "title": "Nurse"}]
    )
    fid_a = uow.fetchone("SELECT id FROM explore_findings WHERE user_id = 1")["id"]
    audit.record(uow, 1, "approve_match", {"finding_id": fid_a})
    # Adversarial: bob's row references ALICE's finding, so only the explicit
    # user_id filter (not the per-finding python filter) stands between tenants.
    audit.record(uow, 2, "approve_match", {"finding_id": fid_a, "note": "bob-secret"})
    uow.commit()

    detail = pipeline.get_match_detail(uow, 1, fid_a)
    assert detail is not None
    serialized = json.dumps(detail, default=str)  # entrypoint-style (PG datetimes)
    assert "bob-secret" not in serialized
    assert [e["event"].split(" ")[0] for e in detail["audit"]] == ["approve_match"]


def test_pipeline_empty_state_for_a_fresh_user(any_uow):
    from mcpforwork.services import pipeline

    uow = any_uow
    uow.execute("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
    uow.commit()
    assert pipeline.list_pipeline(uow, 1) == []
    stats = pipeline.pipeline_stats(uow, 1)
    assert stats["newMatches"] == {"count": 0, "foundThisWeek": 0}
    assert stats["submitted"] == {"count": 0, "verified": 0}
    assert pipeline.get_match_detail(uow, 1, 1) is None


# --------------------------------------------------------------------------- #
# S6.9 — no silent read windows: stats aggregate in SQL, match-detail audit
# is finding-scoped (unrelated audit volume can never crowd out its events)
# --------------------------------------------------------------------------- #
def _iso_ms_z(value: datetime) -> str:
    """The exact shape SQLite's strftime column defaults write (ms + Z)."""
    value = value.astimezone(UTC)
    return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


def test_stats_stay_correct_beyond_the_old_1000_finding_window(any_uow):
    from mcpforwork.services import pipeline

    uow = any_uow
    uow.execute("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
    # 1001 recent new matches (default first_seen = now) + 2 older than a week.
    for i in range(1001):
        uow.execute(
            "INSERT INTO explore_findings (user_id, source_slug, dedup_hash, url, title)"
            " VALUES (1, 'weworkremotely', ?, ?, ?)",
            (f"w{i}", f"https://w.example/{i}", f"Job {i}"),
        )
    old = _iso_ms_z(datetime.now(UTC) - timedelta(days=10))
    for i in range(1001, 1003):
        uow.execute(
            "INSERT INTO explore_findings (user_id, source_slug, dedup_hash, url, title,"
            " first_seen) VALUES (1, 'weworkremotely', ?, ?, ?, ?)",
            (f"w{i}", f"https://w.example/{i}", f"Job {i}", old),
        )
    # One awaiting_you + one verified, ids past the old window's tail.
    for i, state in ((1003, "awaiting_human"), (1004, "verified")):
        fid = uow.insert(
            "INSERT INTO explore_findings (user_id, source_slug, dedup_hash, url, title)"
            " VALUES (1, 'weworkremotely', ?, ?, ?)",
            (f"w{i}", f"https://w.example/{i}", f"Job {i}"),
        )
        uow.insert(
            "INSERT INTO applications (user_id, finding_id, state) VALUES (1, ?, ?)",
            (fid, state),
        )
    uow.commit()

    stats = pipeline.pipeline_stats(uow, 1)
    assert stats["newMatches"] == {"count": 1003, "foundThisWeek": 1001}
    assert stats["needsYou"] == {"count": 1}
    assert stats["submitted"] == {"count": 1, "verified": 1}
    assert stats["responses"] == {"count": 0, "of": 1, "interviews": 0}


_FINDING_STATUSES = ["new", "review", "approved", "discarded", "applied_external"]
_APP_STATES = [
    None,
    "draft",
    "filling",
    "awaiting_human",
    "submit_requested",
    "submitted",
    "verified",
    "abandoned",
]
_OUTCOMES = [None, "", "no_reply", "rejected", "interview", "offer", "hired", "mystery"]


def test_stats_sql_stage_case_agrees_with_derive_stage_on_a_seeded_matrix(any_uow):
    """The SQL CASE in _stage_counts must mirror the pure derive_stage on the
    full (finding status × application state × outcome) matrix — drift between
    the two vocabularies fails here, on both dialects."""
    from collections import Counter

    from mcpforwork.services import pipeline

    uow = any_uow
    uow.execute("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
    expected: Counter[str] = Counter()
    i = 0
    for status in _FINDING_STATUSES:
        for state in _APP_STATES:
            for outcome in _OUTCOMES:
                i += 1
                fid = uow.insert(
                    "INSERT INTO explore_findings (user_id, source_slug, dedup_hash, url,"
                    " title, status) VALUES (1, 'weworkremotely', ?, ?, ?, ?)",
                    (f"m{i}", f"https://m.example/{i}", f"Combo {i}", status),
                )
                app = None
                if state is not None:
                    uow.insert(
                        "INSERT INTO applications (user_id, finding_id, state, outcome)"
                        " VALUES (1, ?, ?, ?)",
                        (fid, state, outcome),
                    )
                    app = {"state": state, "outcome": outcome}
                expected[pipeline.derive_stage(status, app)] += 1
    uow.commit()

    week_start = datetime.now(UTC) - timedelta(days=7)
    counts, recent_new = pipeline._stage_counts(uow, 1, week_start)
    assert counts == dict(expected)
    assert recent_new == expected["new_match"]  # everything seeded just now


def test_stats_never_count_another_users_findings(any_uow):
    """Kills the 'drop the tenant predicate' mutant on the stats SQL: user 2's
    rows must not move user 1's counts, on either dialect."""
    from mcpforwork.services import pipeline

    uow = any_uow
    uow.execute("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
    uow.execute("INSERT INTO users (id, email) VALUES (2, 'b@example.com')")
    uow.execute(
        "INSERT INTO explore_findings (user_id, source_slug, dedup_hash, url, title)"
        " VALUES (1, 'weworkremotely', 'mine', 'https://a.example/1', 'My Job')"
    )
    # Bob: a finding in every stage bucket the stats count, incl. one whose
    # application would land in the same MAX(id) subquery shape.
    for i, status in enumerate(("new", "discarded", "approved")):
        fid = uow.insert(
            "INSERT INTO explore_findings (user_id, source_slug, dedup_hash, url, title,"
            " status) VALUES (2, 'weworkremotely', ?, ?, ?, ?)",
            (f"b{i}", f"https://b.example/{i}", f"Bob Job {i}", status),
        )
        uow.insert(
            "INSERT INTO applications (user_id, finding_id, state) VALUES (2, ?, 'verified')",
            (fid,),
        )
    uow.commit()

    stats = pipeline.pipeline_stats(uow, 1)
    assert stats["newMatches"] == {"count": 1, "foundThisWeek": 1}
    assert stats["needsYou"] == {"count": 0}
    assert stats["submitted"] == {"count": 0, "verified": 0}
    assert stats["responses"] == {"count": 0, "of": 0, "interviews": 0}


def test_stats_use_the_latest_application_per_finding(any_uow):
    """Kills the MAX(id)→MIN(id) mutant: a re-apply whose newest application is
    abandoned leaves the match new, even though an older one was submitted."""
    from mcpforwork.services import pipeline

    uow = any_uow
    uow.execute("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
    fid = uow.insert(
        "INSERT INTO explore_findings (user_id, source_slug, dedup_hash, url, title)"
        " VALUES (1, 'weworkremotely', 'h', 'https://a.example/1', 'Job')"
    )
    uow.insert(
        "INSERT INTO applications (user_id, finding_id, state) VALUES (1, ?, 'submitted')",
        (fid,),
    )
    uow.insert(
        "INSERT INTO applications (user_id, finding_id, state) VALUES (1, ?, 'abandoned')",
        (fid,),
    )
    uow.commit()

    stats = pipeline.pipeline_stats(uow, 1)
    assert stats["newMatches"]["count"] == 1
    assert stats["submitted"] == {"count": 0, "verified": 0}


def test_match_detail_audit_is_complete_beyond_200_unrelated_rows(any_uow):
    from mcpforwork.services import pipeline

    uow = any_uow
    uow.execute("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
    hunt.submit_findings(
        uow, 1, "weworkremotely", [{"url": "https://a.example/1", "title": "Nurse"}]
    )
    fid = uow.fetchone("SELECT id FROM explore_findings WHERE user_id = 1")["id"]
    app_id = uow.insert(
        "INSERT INTO applications (user_id, finding_id, state) VALUES (1, ?, 'submitted')",
        (fid,),
    )
    audit.record(uow, 1, "approve_match", {"finding_id": fid})
    audit.record(uow, 1, "submit_asset", {"finding_id": fid, "asset_type": "cv", "version": 1})
    audit.record(uow, 1, "confirm_submitted", {"application_id": app_id, "evidence": True})
    # 250 unrelated NEWER rows — the old 200-row window pushed the finding's
    # own events out of sight. One adversarial row whose finding_id merely
    # STARTS WITH ours (over-match the pre-filter must not leak through).
    for i in range(250):
        audit.record(uow, 1, "save_form_answer", {"field_label": f"q{i}"})
    audit.record(uow, 1, "approve_match", {"finding_id": int(f"{fid}1")})
    uow.commit()

    detail = pipeline.get_match_detail(uow, 1, fid)
    assert detail is not None
    events = [e["event"].split(" ")[0] for e in detail["audit"]]
    assert events == ["confirm_submitted", "submit_asset", "approve_match"]


# --------------------------------------------------------------------------- #
# MCP tool — one service, two thin wrappers
# --------------------------------------------------------------------------- #
def test_pipeline_stats_mcp_tool_reads_the_same_service(mcp_env, tmp_path):
    uow = connect(mcp_env)
    try:
        uow.execute("INSERT INTO users (id, email) VALUES (1, 'local@self-host')")
        hunt.submit_findings(
            uow, 1, "weworkremotely", [{"url": "https://m.example/1", "title": "Nurse"}]
        )
        uow.commit()
    finally:
        uow.close()
    payload = json.loads(server.pipeline_stats())
    assert payload["newMatches"]["count"] == 1
    assert payload["next_action"]  # breadcrumb present
