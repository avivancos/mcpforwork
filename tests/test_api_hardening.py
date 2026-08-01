"""API hardening, self-host scope (S6.1c): body-size cap, TrustedHost
allowlist, cookie-secure escape hatch, and the live-PG cross-tenant HTTP test.

Zero mocks: real Starlette TestClient on a real tmp SQLite database; the
live arm drives two real magic-link logins against a real Postgres as the
restricted `app` role.
"""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from mcpforwork.entrypoints.api.app import create_app
from mcpforwork.services import hunt

_SECRET = "test-secret-please-rotate"
_MAX_BODY = 64 * 1024


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


def _redeem_response(client: TestClient, mailer: _CapturingMailer, email: str):
    client.post("/v1/auth/magic-link", json={"email": email})
    token = parse_qs(urlparse(mailer.sent[-1][1]).query)["token"][0]
    return client.get(f"/v1/auth/redeem?token={token}")


# --------------------------------------------------------------------------- #
# Body-size cap (64 KB) — the unauthenticated magic-link POST buffers the body
# --------------------------------------------------------------------------- #
def _json_body_of_size(n: int) -> bytes:
    base = len(json.dumps({"email": "ada@example.com", "pad": ""}))
    body = json.dumps({"email": "ada@example.com", "pad": "x" * (n - base)}).encode()
    assert len(body) == n
    return body


def test_a_post_body_over_64kb_is_rejected_413(env):
    client = _client(_CapturingMailer())
    r = client.post(
        "/v1/auth/magic-link",
        content=_json_body_of_size(_MAX_BODY + 1),
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 413


def test_a_post_body_at_the_cap_is_served(env):
    client = _client(_CapturingMailer())
    r = client.post(
        "/v1/auth/magic-link",
        content=_json_body_of_size(_MAX_BODY),
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 202  # the route processed it — the cap did not trip


def test_a_chunked_post_body_over_64kb_is_rejected_413(env):
    # An iterator body has no known length → httpx sends Transfer-Encoding:
    # chunked with NO Content-Length, exercising the stream-counting guard.
    client = _client(_CapturingMailer())
    chunks = iter([b'{"email": "ada@example.com", "pad": "', b"x" * (_MAX_BODY + 1), b'"}'])
    r = client.post(
        "/v1/auth/magic-link", content=chunks, headers={"content-type": "application/json"}
    )
    assert r.status_code == 413


def test_get_requests_are_not_body_capped(env):
    client = _client(_CapturingMailer())
    assert client.get("/v1/profile").status_code == 401  # not a 4xx from the cap


# --------------------------------------------------------------------------- #
# TrustedHost allowlist (DNS-rebinding guard on LAN self-host)
# --------------------------------------------------------------------------- #
def test_a_disallowed_host_header_is_rejected_400(env):
    client = _client(_CapturingMailer())
    assert client.get("/v1/profile", headers={"host": "evil.example.com"}).status_code == 400


def test_the_default_allowlist_serves_local_hosts(env):
    client = _client(_CapturingMailer())
    # 401 (not 400): the host passed the allowlist, auth is what refused.
    assert client.get("/v1/profile").status_code == 401  # testserver
    assert client.get("/v1/profile", headers={"host": "localhost"}).status_code == 401
    assert client.get("/v1/profile", headers={"host": "localhost:8000"}).status_code == 401
    assert client.get("/v1/profile", headers={"host": "127.0.0.1"}).status_code == 401


def test_the_allowlist_is_env_driven(env, monkeypatch):
    monkeypatch.setenv("MCPFORWORK_ALLOWED_HOSTS", "dashboard.lan")
    client = _client(_CapturingMailer())
    assert client.get("/v1/profile", headers={"host": "dashboard.lan"}).status_code == 401
    assert client.get("/v1/profile").status_code == 400  # testserver now rejected


# --------------------------------------------------------------------------- #
# Cookie Secure — default on; MCPFORWORK_COOKIE_SECURE=0 is the LAN-http hatch
# --------------------------------------------------------------------------- #
def _cookie_attrs(set_cookie: str) -> set[str]:
    return {part.strip().lower() for part in set_cookie.split(";")}


def test_the_session_cookie_is_secure_by_default(env):
    mailer = _CapturingMailer()
    client = _client(mailer)
    r = _redeem_response(client, mailer, "ada@example.com")
    assert r.status_code == 200
    assert "secure" in _cookie_attrs(r.headers["set-cookie"])


def test_cookie_secure_env_escape_hatch(env, monkeypatch):
    monkeypatch.setenv("MCPFORWORK_COOKIE_SECURE", "0")
    mailer = _CapturingMailer()
    client = _client(mailer)
    r = _redeem_response(client, mailer, "ada@example.com")
    assert r.status_code == 200
    assert "secure" not in _cookie_attrs(r.headers["set-cookie"])
    assert "httponly" in _cookie_attrs(r.headers["set-cookie"])  # the rest stays


# --------------------------------------------------------------------------- #
# Live-PG: cross-tenant isolation through the HTTP layer, as the restricted
# app role (RLS-bound, no DDL — the request path must not run migrations)
# --------------------------------------------------------------------------- #
@pytest.fixture
def live_pg_api(monkeypatch):
    import pg_support

    if not pg_support.admin_url():
        pytest.skip("TEST_POSTGRES_URL not set")
    admin = pg_support.admin_connect()
    admin.execute("TRUNCATE users, magic_link_tokens RESTART IDENTITY CASCADE")
    admin.commit()
    admin.close()
    monkeypatch.setenv("MCPFORWORK_DB_URL", pg_support.app_url())
    monkeypatch.setenv("MCPFORWORK_DB_RUN_MIGRATIONS", "0")
    monkeypatch.setenv("MCPFORWORK_SESSION_SECRET", _SECRET)
    return _CapturingMailer()


@pytest.mark.live
def test_the_request_path_role_is_non_privileged(live_pg_api):
    import pg_support

    conn = pg_support.app_connect()
    try:
        assert conn.fetchone("SELECT current_user AS r")["r"] == pg_support.APP_ROLE
        row = conn.fetchone(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
        )
        assert row["rolsuper"] is False
        assert row["rolbypassrls"] is False
    finally:
        conn.close()


@pytest.mark.live
def test_live_pg_cross_tenant_isolation_through_the_http_layer(live_pg_api):
    import pg_support

    mailer = live_pg_api
    client_a = _client(mailer)
    _login(client_a, mailer, "ada@example.com")
    client_b = _client(mailer)
    _login(client_b, mailer, "bob@example.com")

    # Bob's finding, seeded as the app role under his tenant context (the same
    # path the MCP server writes through).
    bob = pg_support.app_connect()
    try:
        bob_id = bob.fetchone("SELECT id FROM users WHERE email = 'bob@example.com'")["id"]
        bob.set_user_context(bob_id)
        hunt.submit_findings(
            bob, bob_id, "weworkremotely", [{"url": "https://b.example/1", "title": "Bob Job"}]
        )
        bob_fid = bob.fetchone("SELECT id FROM explore_findings WHERE user_id = ?", (bob_id,))["id"]
        bob.commit()
    finally:
        bob.close()

    # User A cannot reach Bob's data through any route.
    assert client_a.get("/v1/pipeline").json() == []
    assert client_a.get(f"/v1/matches/{bob_fid}").status_code == 404
    assert client_a.post(f"/v1/matches/{bob_fid}/approve").status_code == 404
    assert client_a.post(f"/v1/matches/{bob_fid}/discard").status_code == 404
    assert client_a.get("/v1/audit").json() == []
    sessions_a = client_a.get("/v1/sessions").json()
    assert len(sessions_a) == 1  # exactly her own login session

    # Bob sees his own data through the same stack (the app role can serve
    # every route — grants are correct, no permission errors).
    assert [i["role"] for i in client_b.get("/v1/pipeline").json()] == ["Bob Job"]
    assert client_b.get(f"/v1/matches/{bob_fid}").status_code == 200
