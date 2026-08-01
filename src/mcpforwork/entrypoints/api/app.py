"""Starlette parity API — magic-link session auth + a first slice of read/write
routes, each delegating to an existing service.

Chosen over FastAPI deliberately: Starlette (+uvicorn +httpx) is already
transitive via `mcp`, so this adds no runtime dependency, and the httpx-backed
TestClient gives real, zero-mock HTTP tests. Multi-tenant: the tenant is the
session-cookie's user, resolved per request (unlike the single-user stdio MCP
server), and set as the RLS context on the connection.
"""

from __future__ import annotations

import contextlib
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
from mcpforwork.services import apply as apply_service
from mcpforwork.services import auth_session, hunt, pipeline, privacy, profiles, review

_SESSION_COOKIE = "mcpforwork_session"
_SESSION_MAX_AGE_S = 14 * 24 * 3600  # 14 days

# Web outcome vocabulary (types.ts Outcome) → the service vocabulary
# (services/apply.OUTCOMES).
_WEB_OUTCOMES = {
    "no_response": "no_reply",
    "rejected": "rejected",
    "interview": "interview",
    "offer": "offer",
}


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
            profile = profiles.get_web_profile(uow, user_id)
        finally:
            uow.close()
        return _JSON(profile)

    async def post_profile(request: Request) -> Response:
        user_id = _current_user(request)
        if user_id is None:
            return _unauthorized()
        try:
            body = await request.json()
        except Exception:
            return _JSON({"error": "invalid request"}, status_code=400)
        if not isinstance(body, dict):
            return _JSON({"error": "invalid request"}, status_code=400)
        uow = connect(config.db_url())
        try:
            uow.set_user_context(user_id)
            result = profiles.update_web_profile(uow, user_id, body)
            if "error" in result:
                return _JSON({"error": result["error"]}, status_code=400)
            uow.commit()
        finally:
            uow.close()
        return Response(status_code=204)

    def _match_id(request: Request) -> int | None:
        try:
            return int(request.path_params["id"])
        except (KeyError, ValueError):
            return None

    def _action_response(result: dict[str, Any]) -> Response:
        if "error" in result:
            # Unknown and foreign matches are indistinguishable (both 404).
            status = 404 if "not found" in result["error"] else 400
            return _JSON({"error": result["error"]}, status_code=status)
        return Response(status_code=204)

    async def _match_action(request: Request, action: Any) -> Response:
        user_id = _current_user(request)
        if user_id is None:
            return _unauthorized()
        finding_id = _match_id(request)
        if finding_id is None:
            return _JSON({"error": "not found"}, status_code=404)
        uow = connect(config.db_url())
        try:
            uow.set_user_context(user_id)
            result = action(uow, user_id, finding_id)
            response = _action_response(result)
            if response.status_code == 204:
                uow.commit()
        finally:
            uow.close()
        return response

    async def approve_match_route(request: Request) -> Response:
        return await _match_action(request, review.approve_match)

    async def discard_match_route(request: Request) -> Response:
        reason = ""
        with contextlib.suppress(Exception):
            body = await request.json()
            if isinstance(body, dict):
                reason = str(body.get("reason", ""))
        return await _match_action(
            request, lambda u, uid, fid: review.discard_match(u, uid, fid, reason)
        )

    async def restore_match_route(request: Request) -> Response:
        return await _match_action(request, review.restore_match)

    async def record_outcome_route(request: Request) -> Response:
        user_id = _current_user(request)
        if user_id is None:
            return _unauthorized()
        finding_id = _match_id(request)
        if finding_id is None:
            return _JSON({"error": "not found"}, status_code=404)
        try:
            body = await request.json()
        except Exception:
            return _JSON({"error": "invalid request"}, status_code=400)
        if not isinstance(body, dict):
            return _JSON({"error": "invalid request"}, status_code=400)
        outcome = _WEB_OUTCOMES.get(str(body.get("outcome", "")))
        if outcome is None:
            return _JSON(
                {"error": f"outcome must be one of {sorted(_WEB_OUTCOMES)}"}, status_code=400
            )
        uow = connect(config.db_url())
        try:
            uow.set_user_context(user_id)
            if hunt.get_match(uow, user_id, finding_id) is None:
                return _JSON({"error": "not found"}, status_code=404)
            app = uow.fetchone(
                "SELECT id FROM applications WHERE user_id = ? AND finding_id = ?"
                " ORDER BY id DESC LIMIT 1",
                (user_id, finding_id),
            )
            if app is None:
                return _JSON({"error": "no application for this match yet"}, status_code=400)
            result = apply_service.record_outcome(uow, user_id, app["id"], outcome)
            response = _action_response(result)
            if response.status_code == 204:
                uow.commit()
        finally:
            uow.close()
        return response

    async def list_pipeline_route(request: Request) -> Response:
        user_id = _current_user(request)
        if user_id is None:
            return _unauthorized()
        uow = connect(config.db_url())
        try:
            uow.set_user_context(user_id)
            items = pipeline.list_pipeline(uow, user_id)
        finally:
            uow.close()
        return _JSON(items)

    async def pipeline_stats_route(request: Request) -> Response:
        user_id = _current_user(request)
        if user_id is None:
            return _unauthorized()
        uow = connect(config.db_url())
        try:
            uow.set_user_context(user_id)
            stats = pipeline.pipeline_stats(uow, user_id)
        finally:
            uow.close()
        return _JSON(stats)

    async def get_match_route(request: Request) -> Response:
        user_id = _current_user(request)
        if user_id is None:
            return _unauthorized()
        try:
            finding_id = int(request.path_params["id"])
        except (KeyError, ValueError):
            return _JSON({"error": "not found"}, status_code=404)
        uow = connect(config.db_url())
        try:
            uow.set_user_context(user_id)
            detail = pipeline.get_match_detail(uow, user_id, finding_id)
        finally:
            uow.close()
        if detail is None:
            # 404 → the web's getOrNull maps it to null (foreign ids included).
            return _JSON({"error": "not found"}, status_code=404)
        return _JSON(detail)

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
        Route("/v1/profile", post_profile, methods=["POST"]),
        Route("/v1/pipeline", list_pipeline_route, methods=["GET"]),
        Route("/v1/pipeline/stats", pipeline_stats_route, methods=["GET"]),
        Route("/v1/matches/{id}", get_match_route, methods=["GET"]),
        Route("/v1/matches/{id}/approve", approve_match_route, methods=["POST"]),
        Route("/v1/matches/{id}/discard", discard_match_route, methods=["POST"]),
        Route("/v1/matches/{id}/restore", restore_match_route, methods=["POST"]),
        Route("/v1/matches/{id}/outcome", record_outcome_route, methods=["POST"]),
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
