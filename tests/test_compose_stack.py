"""Compose full stack (S6.8): the api service, the web fixture switch-off,
tenant-email alignment between MCP writer and dashboard login, and the
post-login redeem redirect.

Zero mocks: the compose file is parsed with the project's declared yaml
dependency; API tests run a real TestClient on a real tmp SQLite database;
the MCP alignment tests drive the real server seam on tmp SQLite.
"""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import yaml
from starlette.testclient import TestClient

from mcpforwork.adapters.db import connect
from mcpforwork.entrypoints.api.app import create_app
from mcpforwork.services import auth_session

_SECRET = "test-secret-please-rotate"
_REPO = Path(__file__).resolve().parent.parent


class _CapturingMailer:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_magic_link(self, email: str, link: str) -> None:
        self.sent.append((email, link))


@pytest.fixture
def env(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MCPFORWORK_DB_URL", f"sqlite:///{tmp_path / 'api.db'}")
    monkeypatch.setenv("MCPFORWORK_SESSION_SECRET", _SECRET)
    monkeypatch.delenv("MCPFORWORK_POST_LOGIN_REDIRECT", raising=False)
    monkeypatch.delenv("MCPFORWORK_USER_EMAIL", raising=False)
    return tmp_path


def _client(mailer: _CapturingMailer) -> TestClient:
    return TestClient(
        create_app(mailer=mailer), base_url="https://testserver", raise_server_exceptions=False
    )


def _login(client: TestClient, mailer: _CapturingMailer, email: str) -> None:
    client.post("/v1/auth/magic-link", json={"email": email})
    token = parse_qs(urlparse(mailer.sent[-1][1]).query)["token"][0]
    assert client.get(f"/v1/auth/redeem?token={token}").status_code == 200


# --------------------------------------------------------------------------- #
# docker-compose.yml shape (parsed, not grepped — yaml is a declared dep)
# --------------------------------------------------------------------------- #
def _compose() -> dict:
    return yaml.safe_load((_REPO / "docker-compose.yml").read_text())


def test_compose_has_an_api_service_sharing_the_sqlite_volume():
    services = _compose()["services"]
    api = services["api"]
    assert api["image"] == services["mcp"]["image"]  # same image as mcp
    assert "mcpforwork-data:/data" in api["volumes"]
    assert "uvicorn" in str(api["command"])


def test_the_session_secret_is_required_never_baked():
    raw = (_REPO / "docker-compose.yml").read_text()
    # compose's `:?` errors out with a clear message when the var is unset
    assert "${MCPFORWORK_SESSION_SECRET:?" in raw
    assert "MCPFORWORK_SESSION_SECRET:-" not in raw  # no baked default form


def test_web_points_at_the_real_api_not_fixtures():
    web_env = _compose()["services"]["web"]["environment"]
    assert web_env["MCPFORWORK_API_URL"] == "http://api:8000"
    assert "MCPFORWORK_FIXTURES" not in web_env


def test_both_python_services_carry_the_tenant_email():
    services = _compose()["services"]
    for name in ("mcp", "api"):
        assert "MCPFORWORK_USER_EMAIL" in services[name]["environment"], name


def test_env_example_documents_the_secret_and_tenant_email():
    text = (_REPO / ".env.example").read_text()
    assert "MCPFORWORK_SESSION_SECRET" in text
    assert "MCPFORWORK_USER_EMAIL" in text


# --------------------------------------------------------------------------- #
# Redeem → post-login redirect (fixed config, never client-controlled)
# --------------------------------------------------------------------------- #
def test_redeem_redirects_to_the_configured_post_login_url(env, monkeypatch):
    monkeypatch.setenv("MCPFORWORK_POST_LOGIN_REDIRECT", "http://localhost:2200/pipeline")
    mailer = _CapturingMailer()
    client = _client(mailer)
    client.post("/v1/auth/magic-link", json={"email": "ada@example.com"})
    token = parse_qs(urlparse(mailer.sent[-1][1]).query)["token"][0]
    r = client.get(f"/v1/auth/redeem?token={token}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "http://localhost:2200/pipeline"
    # the session cookie rides the 302 — the login completes through the redirect
    assert "mcpforwork_session=" in r.headers["set-cookie"]


def test_redeem_ignores_a_client_supplied_redirect_param(env, monkeypatch):
    """Open-redirect probe: a ?next=/redirect= param must never override the
    fixed configured target (S6.8 review P2 — kills the client-override mutant).
    """
    monkeypatch.setenv("MCPFORWORK_POST_LOGIN_REDIRECT", "http://localhost:2200/pipeline")
    mailer = _CapturingMailer()
    client = _client(mailer)
    client.post("/v1/auth/magic-link", json={"email": "ada@example.com"})
    token = parse_qs(urlparse(mailer.sent[-1][1]).query)["token"][0]
    r = client.get(
        f"/v1/auth/redeem?token={token}&next=http://evil.example/steal",
        follow_redirects=False,
    )
    assert r.status_code == 302
    assert r.headers["location"] == "http://localhost:2200/pipeline"


def test_redeem_without_a_configured_redirect_stays_json(env):
    mailer = _CapturingMailer()
    client = _client(mailer)
    client.post("/v1/auth/magic-link", json={"email": "ada@example.com"})
    token = parse_qs(urlparse(mailer.sent[-1][1]).query)["token"][0]
    r = client.get(f"/v1/auth/redeem?token={token}", follow_redirects=False)
    assert r.status_code == 200
    assert json.loads(r.text) == {"ok": True}


# --------------------------------------------------------------------------- #
# Tenant alignment: GET /v1/connection surfaces the CONFIGURED tenant email
# --------------------------------------------------------------------------- #
def test_connection_surfaces_the_configured_tenant_email(env, monkeypatch):
    monkeypatch.setenv("MCPFORWORK_USER_EMAIL", "ada@example.com")
    mailer = _CapturingMailer()
    client = _client(mailer)
    _login(client, mailer, "ada@example.com")
    body = client.get("/v1/connection").json()
    assert body["tenantEmail"] == "ada@example.com"


def test_connection_tenant_email_defaults_to_the_self_host_placeholder(env):
    # Logged in as ada@example.com while the MCP writes as local@self-host —
    # the mismatch is VISIBLE in the payload (that is the point of the field).
    mailer = _CapturingMailer()
    client = _client(mailer)
    _login(client, mailer, "ada@example.com")
    body = client.get("/v1/connection").json()
    assert body["tenantEmail"] == "local@self-host"


# --------------------------------------------------------------------------- #
# MCP boot alignment: the local user row is keyed by MCPFORWORK_USER_EMAIL
# --------------------------------------------------------------------------- #
def _mcp_uow(tmp_path: Path, monkeypatch, **env_vars: str):
    from mcpforwork.entrypoints.mcp import server

    monkeypatch.setenv("MCPFORWORK_DB_URL", f"sqlite:///{tmp_path / 'm.db'}")
    monkeypatch.delenv("MCPFORWORK_USER_ID", raising=False)
    monkeypatch.delenv("MCPFORWORK_USER_EMAIL", raising=False)
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return server._uow()


def test_mcp_boot_aligns_the_local_user_to_the_configured_email(tmp_path, monkeypatch):
    uow, user_id = _mcp_uow(tmp_path, monkeypatch, MCPFORWORK_USER_EMAIL="ada@example.com")
    try:
        row = uow.fetchone("SELECT id, email FROM users WHERE id = ?", (user_id,))
        assert row["email"] == "ada@example.com"
    finally:
        uow.close()
    # a second boot resolves the SAME row — find, not create
    uow2, user_id2 = _mcp_uow(tmp_path, monkeypatch, MCPFORWORK_USER_EMAIL="ada@example.com")
    try:
        assert user_id2 == user_id
        assert uow2.fetchone("SELECT COUNT(*) AS n FROM users")["n"] == 1
    finally:
        uow2.close()


def test_mcp_boot_finds_the_row_the_dashboard_login_created(tmp_path, monkeypatch):
    # The dashboard's magic-link find-or-create got there first — the MCP must
    # write as THAT row, not mint a second user.
    uow = connect(f"sqlite:///{tmp_path / 'm.db'}")
    try:
        dash_id = uow.insert("INSERT INTO users (email) VALUES (?)", ("ada@example.com",))
        uow.commit()
    finally:
        uow.close()
    mcp_uow, user_id = _mcp_uow(tmp_path, monkeypatch, MCPFORWORK_USER_EMAIL="ada@example.com")
    try:
        assert user_id == dash_id
        assert mcp_uow.fetchone("SELECT COUNT(*) AS n FROM users")["n"] == 1
    finally:
        mcp_uow.close()


def test_mcp_boot_honors_an_explicit_user_id_pin(tmp_path, monkeypatch):
    uow, user_id = _mcp_uow(tmp_path, monkeypatch, MCPFORWORK_USER_ID="7")
    try:
        assert user_id == 7
        assert uow.fetchone("SELECT email FROM users WHERE id = 7")["email"] == "local@self-host"
    finally:
        uow.close()


def test_mcp_boot_raises_on_a_real_id_email_conflict(tmp_path, monkeypatch):
    # Both vars explicitly set, and the pinned id belongs to another email —
    # a genuine misconfiguration must fail loud, not split the tenant.
    uow = connect(f"sqlite:///{tmp_path / 'm.db'}")
    try:
        uow.execute("INSERT INTO users (id, email) VALUES (1, 'bob@example.com')")
        uow.commit()
    finally:
        uow.close()
    with pytest.raises(RuntimeError, match="MCPFORWORK_USER_ID"):
        _mcp_uow(tmp_path, monkeypatch, MCPFORWORK_USER_ID="1", MCPFORWORK_USER_EMAIL="a@b.c")


def test_mcp_boot_legacy_pin_keeps_the_existing_rows_email(tmp_path, monkeypatch):
    # MCPFORWORK_USER_ID set, email never configured: the existing row IS the
    # tenant (legacy behavior) — its email is left untouched.
    uow = connect(f"sqlite:///{tmp_path / 'm.db'}")
    try:
        uow.execute("INSERT INTO users (id, email) VALUES (1, 'bob@example.com')")
        uow.commit()
    finally:
        uow.close()
    mcp_uow, user_id = _mcp_uow(tmp_path, monkeypatch, MCPFORWORK_USER_ID="1")
    try:
        assert user_id == 1
        assert mcp_uow.fetchone("SELECT email FROM users WHERE id = 1")["email"] == (
            "bob@example.com"
        )
    finally:
        mcp_uow.close()


def test_auth_session_login_and_mcp_boot_resolve_the_same_row(tmp_path, monkeypatch):
    # End-to-end of the alignment: a magic-link request (the dashboard login)
    # and an MCP boot with the same configured email land on one users row.
    monkeypatch.setenv("MCPFORWORK_DB_URL", f"sqlite:///{tmp_path / 'm.db'}")
    uow = connect(f"sqlite:///{tmp_path / 'm.db'}")
    try:
        result = auth_session.request_magic_link(
            uow,
            "ada@example.com",
            now=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )
        uow.commit()
        login_uid = result["user_id"]
    finally:
        uow.close()
    mcp_uow, mcp_uid = _mcp_uow(tmp_path, monkeypatch, MCPFORWORK_USER_EMAIL="ada@example.com")
    try:
        assert mcp_uid == login_uid
    finally:
        mcp_uow.close()
