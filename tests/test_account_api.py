"""Account API (S6.6c): sessions store + account read routes.

GET /v1/sessions, POST /v1/sessions/{id}/revoke, GET /v1/audit,
GET /v1/connection, GET /v1/subscription, POST /v1/billing/session — plus the
session-store-backed `_current_user` (revoked / deleted-user / legacy cookies
all die at the DB check).

Zero mocks: real Starlette TestClient on a real tmp SQLite database.
"""

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from mcpforwork.adapters.db import connect
from mcpforwork.entrypoints.api.app import create_app
from mcpforwork.services import hunt

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
    # Hermetic: tenant-email / redirect config from the developer's shell must
    # not leak into these tests (S6.8 review P2).
    monkeypatch.delenv("MCPFORWORK_USER_EMAIL", raising=False)
    monkeypatch.delenv("MCPFORWORK_POST_LOGIN_REDIRECT", raising=False)
    return tmp_path


def _client(mailer: _CapturingMailer) -> TestClient:
    return TestClient(
        create_app(mailer=mailer), base_url="https://testserver", raise_server_exceptions=False
    )


def _login(client: TestClient, mailer: _CapturingMailer, email: str, ua: str = "TestBrowser/1.0"):
    client.post("/v1/auth/magic-link", json={"email": email})
    token = parse_qs(urlparse(mailer.sent[-1][1]).query)["token"][0]
    r = client.get(f"/v1/auth/redeem?token={token}", headers={"user-agent": ua})
    assert r.status_code == 200


@pytest.fixture
def api(env):
    mailer = _CapturingMailer()
    client = _client(mailer)
    _login(client, mailer, "ada@example.com")
    return client, mailer, env


def _uid(env, email="ada@example.com") -> int:
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        return uow.fetchone("SELECT id FROM users WHERE email = ?", (email,))["id"]
    finally:
        uow.close()


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def test_account_routes_require_authentication(env):
    client = _client(_CapturingMailer())
    assert client.get("/v1/sessions").status_code == 401
    assert client.post("/v1/sessions/1/revoke").status_code == 401
    assert client.get("/v1/audit").status_code == 401
    assert client.get("/v1/connection").status_code == 401
    assert client.get("/v1/subscription").status_code == 401
    assert client.post("/v1/billing/session", json={"kind": "portal"}).status_code == 401


# --------------------------------------------------------------------------- #
# Sessions
# --------------------------------------------------------------------------- #
def test_sessions_list_shows_each_login_with_the_current_one_flagged(env):
    mailer = _CapturingMailer()
    a = _client(mailer)
    _login(a, mailer, "ada@example.com", ua="LaptopBrowser/1.0")
    b = _client(mailer)
    _login(b, mailer, "ada@example.com", ua="PhoneBrowser/2.0")

    sessions = b.get("/v1/sessions").json()
    assert len(sessions) == 2
    current = [s for s in sessions if s["current"]]
    assert len(current) == 1
    assert current[0]["device"] == "PhoneBrowser/2.0"
    assert "T" in current[0]["lastSeen"]  # ISO-8601


def test_revoking_the_other_session_kills_its_cookie(env):
    mailer = _CapturingMailer()
    a = _client(mailer)
    _login(a, mailer, "ada@example.com")
    b = _client(mailer)
    _login(b, mailer, "ada@example.com")

    a_sessions = a.get("/v1/sessions").json()
    other = next(s for s in a_sessions if not s["current"])
    assert a.post(f"/v1/sessions/{other['id']}/revoke").status_code == 204
    # b's cookie is now dead at the DB check, even though its HMAC is valid
    assert b.get("/v1/sessions").status_code == 401


def test_revoking_the_current_session_clears_the_cookie(api):
    client, _, _ = api
    current = next(s for s in client.get("/v1/sessions").json() if s["current"])
    r = client.post(f"/v1/sessions/{current['id']}/revoke")
    assert r.status_code == 204
    assert "max-age=0" in r.headers.get("set-cookie", "").lower()
    assert client.get("/v1/sessions").status_code == 401


def test_revoking_a_foreign_session_is_404(api):
    client, mailer, env = api
    bob = _client(mailer)
    _login(bob, mailer, "bob@example.com")
    bob_session = bob.get("/v1/sessions").json()[0]
    assert client.post(f"/v1/sessions/{bob_session['id']}/revoke").status_code == 404
    # bob's session is untouched
    assert bob.get("/v1/sessions").status_code == 200


def test_a_deleted_users_other_sessions_die(api):
    client, mailer, _ = api
    second = _client(mailer)
    _login(second, mailer, "ada@example.com")
    assert client.post("/v1/account/delete").status_code == 200
    # the second cookie outlives the account — the DB check must refuse it
    assert second.get("/v1/sessions").status_code == 401


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
def test_audit_lists_the_users_own_rows_newest_first(api):
    client, _, env = api
    uid = _uid(env)
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        hunt.submit_findings(
            uow, uid, "weworkremotely", [{"url": "https://a.example/1", "title": "Nurse"}]
        )
        fid = uow.fetchone("SELECT id FROM explore_findings WHERE user_id = ?", (uid,))["id"]
        from mcpforwork.services import review

        review.approve_match(uow, uid, fid)
        uow.commit()
    finally:
        uow.close()

    entries = client.get("/v1/audit").json()
    events = [e["event"] for e in entries]
    assert events[0].startswith("approve_match")  # newest first
    assert any(e.startswith("submit_findings") for e in events)
    assert all("T" in e["at"] for e in entries)  # ISO-8601


def test_audit_never_shows_another_users_rows(api):
    client, _, env = api
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        uow.execute("INSERT INTO users (email) VALUES ('bob@example.com')")
        bob = uow.fetchone("SELECT id FROM users WHERE email = 'bob@example.com'")["id"]
        hunt.submit_findings(
            uow, bob, "weworkremotely", [{"url": "https://b.example/secret", "title": "Secret"}]
        )
        uow.commit()
    finally:
        uow.close()
    body = client.get("/v1/audit").text
    assert "b.example" not in body


# --------------------------------------------------------------------------- #
# Connection / subscription / billing
# --------------------------------------------------------------------------- #
def test_connection_reflects_real_activity_and_the_tenant_email(api):
    client, _, env = api
    fresh = client.get("/v1/connection").json()
    assert fresh["connected"] is False
    # tenantEmail is the CONFIGURED MCP tenant email (S6.8), not the session
    # email — a login under a different address shows the mismatch here.
    assert fresh["tenantEmail"] == "local@self-host"

    uid = _uid(env)
    uow = connect(f"sqlite:///{env / 'api.db'}")
    try:
        hunt.submit_findings(
            uow, uid, "weworkremotely", [{"url": "https://a.example/1", "title": "Nurse"}]
        )
        uow.commit()
    finally:
        uow.close()
    after = client.get("/v1/connection").json()
    assert after["connected"] is True
    assert after["client"] is None  # the API cannot know which agent connected
    assert after["syncedMinAgo"] >= 0


def test_subscription_is_the_honest_self_host_stub(api):
    client, _, _ = api
    body = client.get("/v1/subscription").json()
    assert body == {"status": "active", "trialDaysLeft": 0, "price": "self-host"}


def test_billing_session_is_null_until_stripe_lands(api):
    client, _, _ = api
    r = client.post("/v1/billing/session", json={"kind": "checkout"})
    assert r.status_code == 200
    assert r.json() == {"url": None}
