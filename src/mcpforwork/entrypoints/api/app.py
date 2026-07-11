"""Starlette parity API — magic-link session auth + a first slice of read/write
routes, each delegating to an existing service.

Chosen over FastAPI deliberately: Starlette (+uvicorn +httpx) is already
transitive via `mcp`, so this adds no runtime dependency, and the httpx-backed
TestClient gives real, zero-mock HTTP tests. Multi-tenant: the tenant is the
session-cookie's user, resolved per request (unlike the single-user stdio MCP
server), and set as the RLS context on the connection.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from mcpforwork import config
from mcpforwork.adapters.db import connect
from mcpforwork.adapters.mailer import ConsoleMailer
from mcpforwork.ports.mailer import Mailer
from mcpforwork.services import auth_session, privacy, profiles

_SESSION_COOKIE = "mcpforwork_session"
_SESSION_MAX_AGE_S = 14 * 24 * 3600  # 14 days


def _now() -> datetime:
    return datetime.now(UTC)


def _session_secret() -> str:
    """The HMAC key for session cookies. Fail-closed: an unset secret raises
    (→ 5xx) rather than minting an unsigned/guessable session."""
    secret = os.environ.get("MCPFORWORK_SESSION_SECRET")
    if not secret:
        raise RuntimeError("MCPFORWORK_SESSION_SECRET is required to issue/read sessions")
    return secret


def _public_base_url(request: Request) -> str:
    """The trusted origin for the magic-link URL. In any hosted deploy this MUST
    be the configured `MCPFORWORK_PUBLIC_BASE_URL` — never the client-controlled
    Host header, which an attacker could spoof to have a VALID single-use token
    delivered to an origin they control (link poisoning → account takeover). The
    request origin is used only as the self-host/localhost fallback."""
    configured = os.environ.get("MCPFORWORK_PUBLIC_BASE_URL")
    return (configured or str(request.base_url)).rstrip("/")


def _json_default(obj: Any) -> str:
    # Postgres returns datetime objects; SQLite returns ISO strings. Normalise so
    # either backend serialises. (Local to this entrypoint — entrypoints stay
    # independent, so this is not shared with the MCP server's copy.)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


class _JSON(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(content, default=_json_default).encode("utf-8")


def _current_user(request: Request) -> int | None:
    """The signed-in user id from the session cookie, or None."""
    cookie = request.cookies.get(_SESSION_COOKIE)
    if not cookie:
        return None
    return auth_session.read_session(cookie, secret=_session_secret(), now=_now())


def _unauthorized() -> Response:
    return _JSON({"error": "unauthorized"}, status_code=401)


def create_app(mailer: Mailer | None = None) -> Starlette:
    mailer = mailer or ConsoleMailer()

    async def request_magic_link(request: Request) -> Response:
        try:
            body = await request.json()
        except Exception:
            return _JSON({"error": "invalid request"}, status_code=400)
        if not isinstance(body, dict):  # a JSON array/scalar has no .get
            return _JSON({"error": "invalid request"}, status_code=400)
        email = str(body.get("email", ""))
        uow = connect(config.db_url())
        try:
            result = auth_session.request_magic_link(uow, email, now=_now())
            if "error" in result:
                # Uniform 400 — do not disclose whether the email is valid/known.
                return _JSON({"error": "invalid request"}, status_code=400)
            uow.commit()
        finally:
            uow.close()
        link = f"{_public_base_url(request)}/v1/auth/redeem?token={result['raw_token']}"
        # Deliver the NORMALIZED address (validated free of control chars), never
        # the raw client input (SMTP header-injection guard for a real mailer).
        mailer.send_magic_link(result["email"], link)
        # 202 Accepted — the token is delivered out-of-band, NEVER in this body.
        return _JSON({"ok": True}, status_code=202)

    async def redeem(request: Request) -> Response:
        token = request.query_params.get("token", "")
        uow = connect(config.db_url())
        try:
            result = auth_session.redeem_magic_link(uow, token, now=_now())
            if "error" in result:
                return _JSON({"error": "invalid or expired link"}, status_code=400)
            uow.commit()
        finally:
            uow.close()
        cookie = auth_session.issue_session(
            result["user_id"], secret=_session_secret(), now=_now(), max_age_s=_SESSION_MAX_AGE_S
        )
        response = _JSON({"ok": True})
        response.set_cookie(
            _SESSION_COOKIE,
            cookie,
            max_age=_SESSION_MAX_AGE_S,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
        return response

    async def get_profile(request: Request) -> Response:
        user_id = _current_user(request)
        if user_id is None:
            return _unauthorized()
        uow = connect(config.db_url())
        try:
            uow.set_user_context(user_id)
            profile = profiles.get_profile(uow, user_id)
        finally:
            uow.close()
        return _JSON(profile)  # null when the user has no profile yet

    async def account_export(request: Request) -> Response:
        user_id = _current_user(request)
        if user_id is None:
            return _unauthorized()
        uow = connect(config.db_url())
        try:
            uow.set_user_context(user_id)
            export = privacy.export_user_data(uow, user_id)
        finally:
            uow.close()
        return _JSON(export)

    async def account_delete(request: Request) -> Response:
        user_id = _current_user(request)
        if user_id is None:
            return _unauthorized()
        uow = connect(config.db_url())
        try:
            uow.set_user_context(user_id)
            privacy.delete_user_data(uow, user_id)
            uow.commit()
        finally:
            uow.close()
        # Erase the now-dangling session so the deleted account can't keep
        # presenting a still-valid signed cookie for its 14-day life.
        response = _JSON({"ok": True})
        response.delete_cookie(_SESSION_COOKIE, path="/")
        return response

    routes = [
        Route("/v1/auth/magic-link", request_magic_link, methods=["POST"]),
        Route("/v1/auth/redeem", redeem, methods=["GET"]),
        Route("/v1/profile", get_profile, methods=["GET"]),
        Route("/v1/account/export", account_export, methods=["POST"]),
        Route("/v1/account/delete", account_delete, methods=["POST"]),
    ]
    return Starlette(routes=routes)


app = create_app()


def serve() -> None:  # pragma: no cover - process launcher
    """Run the API over uvicorn (the hosted networked entrypoint)."""
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("MCPFORWORK_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("MCPFORWORK_API_PORT", "8080")),
    )
