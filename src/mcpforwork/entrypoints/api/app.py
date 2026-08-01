"""Starlette parity API — magic-link session auth + the dashboard routes, each
delegating to an existing service.

Chosen over FastAPI deliberately: Starlette (+uvicorn +httpx) is already
transitive via `mcp`, so this adds no runtime dependency, and the httpx-backed
TestClient gives real, zero-mock HTTP tests. Multi-tenant: the tenant is the
session-cookie's user, resolved per request (unlike the single-user stdio MCP
server), and set as the RLS context on the connection.

Sessions are backed by the `sessions` table (S6.6c): the signed cookie carries
the session id, and `_current_user` verifies the row is still alive — revoked
sessions, deleted users, and pre-session-store cookies all get 401.
"""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from mcpforwork import config
from mcpforwork.adapters.db import connect
from mcpforwork.adapters.mailer import ConsoleMailer
from mcpforwork.ports.mailer import Mailer
from mcpforwork.services import apply as apply_service
from mcpforwork.services import (
    audit,
    auth_session,
    hunt,
    pipeline,
    privacy,
    profiles,
    review,
)

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

# An agent is "connected" when it acted within this window (audit rows are the
# only signal the server has — it never sees the MCP transport itself).
_CONNECTED_WINDOW_S = 24 * 3600

# Body-size cap (S6.1c): the unauthenticated magic-link POST buffers
# `await request.json()` — without a cap that is a memory-DoS vector.
_MAX_BODY_BYTES = 64 * 1024
_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})


class _BodySizeCap:
    """Pure-ASGI body cap. Fast path: a declared Content-Length over the cap is
    rejected without reading a byte. A body with no declared length (chunked)
    is buffered — bounded at cap+1 — and replayed to the app as a single
    message; over the cap the middleware answers 413 itself. Buffering here
    (not an exception from the receive channel) because the routes' blanket
    `except Exception` around `request.json()` would swallow a raised signal.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = _MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in _BODY_METHODS:
            await self.app(scope, receive, send)
            return
        declared: int | None = None
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = None  # untrustworthy header — the buffered path decides
                break
        if declared is not None:
            if declared > self.max_bytes:
                await self._reject(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return  # client gone — nothing to serve
            body.extend(message.get("body", b""))
            if len(body) > self.max_bytes:
                await self._reject(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        sent = False

        async def replay() -> Any:
            nonlocal sent
            if sent:
                return {"type": "http.request", "body": b"", "more_body": False}
            sent = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        await _JSON({"error": "payload too large"}, status_code=413)(scope, receive, send)


def _allowed_hosts() -> list[str]:
    """TrustedHost allowlist (DNS-rebinding guard on LAN self-host). Default
    serves local clients only — including httpx's dummy `testserver` host,
    which never resolves and has no rebinding surface. IPv6 `::1` is absent on
    purpose: TrustedHostMiddleware splits the Host header on ':', so a
    bracketed IPv6 literal could never match. Set MCPFORWORK_ALLOWED_HOSTS
    (comma-separated) to expose the API on a LAN hostname."""
    raw = os.environ.get("MCPFORWORK_ALLOWED_HOSTS")
    if raw:
        return [h.strip() for h in raw.split(",") if h.strip()]
    return ["localhost", "127.0.0.1", "testserver"]


def _cookie_secure() -> bool:
    """`Secure` on the session cookie. Default on; MCPFORWORK_COOKIE_SECURE=0
    is the documented escape hatch for LAN-http self-host (no TLS), where a
    Secure cookie is never stored and magic-link login could not work."""
    return os.environ.get("MCPFORWORK_COOKIE_SECURE", "1") != "0"


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


def _as_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class _JSON(JSONResponse):
    def render(self, content: Any) -> bytes:
        return json.dumps(content, default=_json_default).encode("utf-8")


def _current_user(request: Request, uow: Any) -> dict[str, int] | None:
    """The signed-in session {"uid", "sid"} from the cookie + session store.

    Sets the RLS user context from the SIGNED cookie's uid as a side effect, so
    the sessions lookup itself runs inside the tenant wall. Refuses (None):
    missing/tampered/expired cookies, pre-session-store cookies (no sid — force
    re-login), revoked or foreign sessions, and deleted users (the cookie dies
    with the account, closing the SQLite rowid-reuse hole)."""
    cookie = request.cookies.get(_SESSION_COOKIE)
    if not cookie:
        return None
    data = auth_session.read_session(cookie, secret=_session_secret(), now=_now())
    if data is None:
        return None
    uid, sid = data["uid"], data.get("sid")
    if sid is None:
        return None
    uow.set_user_context(uid)
    session = auth_session.get_session(uow, sid)
    if session is None or session["revoked_at"] is not None or session["user_id"] != uid:
        return None
    if uow.fetchone("SELECT id FROM users WHERE id = ?", (uid,)) is None:
        return None
    auth_session.touch_session(uow, sid, now=_now())
    # Session bookkeeping commits independently — the route's own work has not
    # started yet, so this can never half-commit a route's writes.
    uow.commit()
    return {"uid": uid, "sid": sid}


def _unauthorized() -> Response:
    return _JSON({"error": "unauthorized"}, status_code=401)


def _connect() -> Any:
    """The request-path connection. `run_migrations` is config-driven so the
    restricted Postgres `app` role (no DDL) can serve requests."""
    return connect(config.db_url(), run_migrations=config.db_run_migrations())


@contextlib.contextmanager
def _authed(request: Request) -> Iterator[tuple[Any, dict[str, int] | None]]:
    """The per-route seam: an open UnitOfWork + the resolved session (or None).
    Mirrors the MCP server's `_tenant_uow` pattern."""
    uow = _connect()
    try:
        yield uow, _current_user(request, uow)
    finally:
        uow.close()


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
        uow = _connect()
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
        uow = _connect()
        try:
            result = auth_session.redeem_magic_link(uow, token, now=_now())
            if "error" in result:
                return _JSON({"error": "invalid or expired link"}, status_code=400)
            # The user just proved this identity — scope the connection before
            # minting the session row (sessions is RLS-forced on Postgres).
            uow.set_user_context(result["user_id"])
            cookie = auth_session.issue_session(
                uow,
                result["user_id"],
                secret=_session_secret(),
                now=_now(),
                max_age_s=_SESSION_MAX_AGE_S,
                user_agent=request.headers.get("user-agent", ""),
            )
            uow.commit()
        finally:
            uow.close()
        response = _JSON({"ok": True})
        response.set_cookie(
            _SESSION_COOKIE,
            cookie,
            max_age=_SESSION_MAX_AGE_S,
            httponly=True,
            secure=_cookie_secure(),
            samesite="lax",
            path="/",
        )
        return response

    async def get_profile(request: Request) -> Response:
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            return _JSON(profiles.get_web_profile(uow, auth["uid"]))

    async def post_profile(request: Request) -> Response:
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            try:
                body = await request.json()
            except Exception:
                return _JSON({"error": "invalid request"}, status_code=400)
            if not isinstance(body, dict):
                return _JSON({"error": "invalid request"}, status_code=400)
            result = profiles.update_web_profile(uow, auth["uid"], body)
            if "error" in result:
                return _JSON({"error": result["error"]}, status_code=400)
            uow.commit()
            return Response(status_code=204)

    def _match_id(request: Request) -> int | None:
        try:
            return int(request.path_params["id"])
        except (KeyError, ValueError):
            return None

    # Structured error kinds → HTTP status (S6.10 — no substring sniffing).
    # Unknown and foreign matches are indistinguishable (both not_found → 404).
    _KIND_STATUS = {"not_found": 404, "invalid_state": 400, "invalid_input": 400}

    def _action_response(result: dict[str, Any]) -> Response:
        if "error" in result:
            status = _KIND_STATUS.get(result.get("kind", ""), 400)
            return _JSON({"error": result["error"]}, status_code=status)
        return Response(status_code=204)

    async def _match_action(request: Request, action: Any) -> Response:
        finding_id = _match_id(request)
        if finding_id is None:
            return _JSON({"error": "not found"}, status_code=404)
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            response = _action_response(action(uow, auth["uid"], finding_id))
            if response.status_code == 204:
                uow.commit()
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
        finding_id = _match_id(request)
        if finding_id is None:
            return _JSON({"error": "not found"}, status_code=404)
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
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
            if hunt.get_match(uow, auth["uid"], finding_id) is None:
                return _JSON({"error": "not found"}, status_code=404)
            app = uow.fetchone(
                "SELECT id FROM applications WHERE user_id = ? AND finding_id = ?"
                " ORDER BY id DESC LIMIT 1",
                (auth["uid"], finding_id),
            )
            if app is None:
                return _JSON({"error": "no application for this match yet"}, status_code=400)
            response = _action_response(
                apply_service.record_outcome(uow, auth["uid"], app["id"], outcome)
            )
            if response.status_code == 204:
                uow.commit()
            return response

    async def list_pipeline_route(request: Request) -> Response:
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            return _JSON(pipeline.list_pipeline(uow, auth["uid"]))

    async def pipeline_stats_route(request: Request) -> Response:
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            return _JSON(pipeline.pipeline_stats(uow, auth["uid"]))

    async def get_match_route(request: Request) -> Response:
        finding_id = _match_id(request)
        if finding_id is None:
            return _JSON({"error": "not found"}, status_code=404)
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            detail = pipeline.get_match_detail(uow, auth["uid"], finding_id)
            if detail is None:
                # 404 → the web's getOrNull maps it to null (foreign ids too).
                return _JSON({"error": "not found"}, status_code=404)
            return _JSON(detail)

    async def list_sessions_route(request: Request) -> Response:
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            rows = auth_session.list_sessions(uow, auth["uid"])
            return _JSON(
                [
                    {
                        "id": str(row["id"]),
                        "device": row["user_agent"] or "Unknown device",
                        "lastSeen": row["last_seen"],
                        "current": row["id"] == auth["sid"],
                    }
                    for row in rows
                ]
            )

    async def revoke_session_route(request: Request) -> Response:
        try:
            session_id = int(request.path_params["id"])
        except (KeyError, ValueError):
            return _JSON({"error": "not found"}, status_code=404)
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            if not auth_session.revoke_session(uow, auth["uid"], session_id, now=_now()):
                # Unknown, foreign, or already revoked — indistinguishable.
                return _JSON({"error": "not found"}, status_code=404)
            uow.commit()
            response = Response(status_code=204)
            if session_id == auth["sid"]:
                # Revoking the CURRENT session logs this browser out too.
                response.delete_cookie(_SESSION_COOKIE, path="/")
            return response

    async def list_audit_route(request: Request) -> Response:
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            return _JSON(audit.recent(uow, auth["uid"]))

    async def get_connection_route(request: Request) -> Response:
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            email = uow.fetchone("SELECT email FROM users WHERE id = ?", (auth["uid"],))["email"]
            last = uow.fetchone(
                "SELECT created_at FROM audit_log WHERE user_id = ? ORDER BY id DESC LIMIT 1",
                (auth["uid"],),
            )
            if last is None:
                # Never synced: -1 is the honest sentinel (the web renders it).
                return _JSON(
                    {
                        "connected": False,
                        "client": None,
                        "syncedMinAgo": -1,
                        "tenantEmail": email,
                    }
                )
            age_s = (_now() - _as_dt(last["created_at"])).total_seconds()
            return _JSON(
                {
                    "connected": age_s <= _CONNECTED_WINDOW_S,
                    "client": None,  # the API cannot know which agent connected
                    "syncedMinAgo": max(0, int(age_s // 60)),
                    "tenantEmail": email,
                }
            )

    async def get_subscription_route(request: Request) -> Response:
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            # Self-host: no billing. Honest static stub (Stripe is S7.1,
            # deferred — hosted track is out of scope).
            return _JSON({"status": "active", "trialDaysLeft": 0, "price": "self-host"})

    async def billing_session_route(request: Request) -> Response:
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            return _JSON({"url": None})

    async def account_export(request: Request) -> Response:
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            return _JSON(privacy.export_user_data(uow, auth["uid"]))

    async def account_delete(request: Request) -> Response:
        with _authed(request) as (uow, auth):
            if auth is None:
                return _unauthorized()
            privacy.delete_user_data(uow, auth["uid"])
            uow.commit()
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
        Route("/v1/sessions", list_sessions_route, methods=["GET"]),
        Route("/v1/sessions/{id}/revoke", revoke_session_route, methods=["POST"]),
        Route("/v1/audit", list_audit_route, methods=["GET"]),
        Route("/v1/connection", get_connection_route, methods=["GET"]),
        Route("/v1/subscription", get_subscription_route, methods=["GET"]),
        Route("/v1/billing/session", billing_session_route, methods=["POST"]),
        Route("/v1/account/export", account_export, methods=["POST"]),
        Route("/v1/account/delete", account_delete, methods=["POST"]),
    ]
    middleware = [
        # Outermost first: reject a spoofed Host before any body is read.
        # www_redirect=False — an API answers 400, it never redirects.
        Middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts(), www_redirect=False),
        Middleware(_BodySizeCap),
    ]
    return Starlette(routes=routes, middleware=middleware)


app = create_app()


def serve() -> None:  # pragma: no cover - process launcher
    """Run the API over uvicorn (the hosted networked entrypoint)."""
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("MCPFORWORK_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("MCPFORWORK_API_PORT", "8080")),
    )
