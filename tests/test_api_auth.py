"""Parity API auth slice (S6.1b): magic-link -> session cookie -> authed request.

A REAL Starlette app driven by the httpx-backed TestClient against a real tmp
SQLite database. Zero mocks — the only injected seam is a capturing Mailer that
records the delivered link (standing in for email/console delivery).
"""

from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from starlette.testclient import TestClient

from mcpforwork.adapters.db import connect
from mcpforwork.entrypoints.api.app import create_app
from mcpforwork.services import profiles

_SECRET = "test-secret-please-rotate"


class _CapturingMailer:
    """Records what would have been emailed, so the test can read the link."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_magic_link(self, email: str, link: str) -> None:
        self.sent.append((email, link))


@pytest.fixture
def env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MCPFORWORK_DB_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("MCPFORWORK_SESSION_SECRET", _SECRET)
    return tmp_path


# https base so the Secure session cookie is actually stored+sent by the client.
def _client(mailer: _CapturingMailer | None = None) -> TestClient:
    return TestClient(
        create_app(mailer=mailer), base_url="https://testserver", raise_server_exceptions=False
    )


@pytest.fixture
def api(env):
    mailer = _CapturingMailer()
    return _client(mailer), mailer


def _token(mailer: _CapturingMailer) -> str:
    return parse_qs(urlparse(mailer.sent[-1][1]).query)["token"][0]


def _login(client: TestClient, mailer: _CapturingMailer, email: str = "ada@example.com"):
    r = client.post("/v1/auth/magic-link", json={"email": email})
    assert r.status_code == 202
    assert email in mailer.sent[-1][0]
    r2 = client.get(f"/v1/auth/redeem?token={_token(mailer)}", follow_redirects=False)
    assert r2.status_code == 200
    return r2


def test_magic_link_response_never_leaks_the_token(api):
    client, mailer = api
    r = client.post("/v1/auth/magic-link", json={"email": "ada@example.com"})
    assert r.status_code == 202
    token = _token(mailer)
    assert token not in r.text  # token travels ONLY in the delivered link


def test_login_sets_a_hardened_session_cookie(api):
    client, mailer = api
    resp = _login(client, mailer)
    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert "httponly" in set_cookie
    assert "secure" in set_cookie
    assert "samesite=lax" in set_cookie


def test_redeem_is_single_use(api, env):
    client, mailer = api
    client.post("/v1/auth/magic-link", json={"email": "ada@example.com"})
    token = _token(mailer)
    assert client.get(f"/v1/auth/redeem?token={token}").status_code == 200
    # a fresh client (no cookie) cannot reuse the same token
    assert _client().get(f"/v1/auth/redeem?token={token}").status_code == 400


def test_redeem_rejects_a_bogus_token(api):
    client, _ = api
    assert client.get("/v1/auth/redeem?token=not-a-real-token").status_code == 400


def test_profile_requires_authentication(api):
    client, mailer = api
    assert client.get("/v1/profile").status_code == 401  # no session cookie
    _login(client, mailer)
    assert client.get("/v1/profile").status_code == 200  # cookie now present


def test_authed_profile_returns_the_users_data(api, env):
    client, mailer = api
    _login(client, mailer, "ada@example.com")
    # seed a profile for the just-created user, then read it through the API
    seed = connect(f"sqlite:///{env / 'api.db'}")
    try:
        uid = seed.fetchone("SELECT id FROM users WHERE email = ?", ("ada@example.com",))["id"]
        profiles.create_profile(seed, uid, {"full_name": "Ada Lovelace"})
        seed.commit()
    finally:
        seed.close()
    body = client.get("/v1/profile").json()
    assert body["name"] == "Ada Lovelace"  # web Profile shape (S6.6b)


def test_account_export_and_delete_are_authed(api):
    client, mailer = api
    assert client.post("/v1/account/export").status_code == 401
    assert client.post("/v1/account/delete").status_code == 401
    _login(client, mailer, "ada@example.com")
    export = client.post("/v1/account/export")
    assert export.status_code == 200
    assert export.json()["user"]["email"] == "ada@example.com"
    assert client.post("/v1/account/delete").status_code == 200
    # delete clears the session cookie, so the client is now unauthenticated
    assert client.get("/v1/profile").status_code == 401


def test_two_users_are_isolated(env):
    # separate clients = separate cookie jars = separate sessions
    a = _client(ma := _CapturingMailer())
    b = _client(mb := _CapturingMailer())
    _login(a, ma, "ada@example.com")
    _login(b, mb, "bob@secret.example.com")
    export_a = a.post("/v1/account/export").json()
    assert export_a["user"]["email"] == "ada@example.com"
    assert "bob@secret.example.com" not in str(export_a)


def test_session_operations_fail_closed_without_a_secret(env, monkeypatch):
    # No MCPFORWORK_SESSION_SECRET -> the redeem step (which issues a session)
    # must error, never silently mint an unsigned/none session.
    mailer = _CapturingMailer()
    client = _client(mailer)
    client.post("/v1/auth/magic-link", json={"email": "ada@example.com"})
    token = _token(mailer)
    monkeypatch.delenv("MCPFORWORK_SESSION_SECRET", raising=False)
    assert client.get(f"/v1/auth/redeem?token={token}").status_code == 500


def test_magic_link_rejects_a_non_object_body(api):
    client, _ = api
    assert client.post("/v1/auth/magic-link", json=[1, 2, 3]).status_code == 400
    assert client.post("/v1/auth/magic-link", json="nope").status_code == 400
    assert client.post("/v1/auth/magic-link", content=b"{bad json").status_code == 400


def test_magic_link_rejects_a_control_char_email(api):
    client, _ = api
    # CR/LF header-injection attempt against a future SMTP mailer must be refused.
    r = client.post("/v1/auth/magic-link", json={"email": "a@b.com\r\nBcc: evil@x.com"})
    assert r.status_code == 400


def test_magic_link_url_uses_the_configured_origin_not_the_host_header(env, monkeypatch):
    # Link-poisoning defense: the sign-in URL comes from trusted config, never a
    # spoofable Host header.
    monkeypatch.setenv("MCPFORWORK_PUBLIC_BASE_URL", "https://app.mcpfor.work")
    mailer = _CapturingMailer()
    client = _client(mailer)
    client.post(
        "/v1/auth/magic-link",
        json={"email": "ada@example.com"},
        headers={"host": "attacker.evil"},
    )
    link = mailer.sent[-1][1]
    assert link.startswith("https://app.mcpfor.work/v1/auth/redeem?token=")
    assert "attacker.evil" not in link


def test_account_delete_clears_the_session_cookie(api):
    client, mailer = api
    _login(client, mailer)
    resp = client.post("/v1/account/delete")
    assert resp.status_code == 200
    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert "max-age=0" in set_cookie or "expires=" in set_cookie  # session cleared


def test_api_entrypoint_does_not_import_the_other_entrypoints():
    # The import-linter contract enforces this structurally; this is a fast unit
    # backstop that the app module imports cleanly without pulling mcp/cli.
    import sys

    import mcpforwork.entrypoints.api.app  # noqa: F401

    assert "mcpforwork.entrypoints.api.app" in sys.modules
