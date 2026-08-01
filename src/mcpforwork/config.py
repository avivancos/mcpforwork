"""Cross-cutting runtime configuration for the driving entrypoints.

Resolved on every call (never cached) so tests and callers can change the
environment. Entrypoints import this to build a UnitOfWork and resolve the
self-host identity; services never do (they take an injected `uow`).
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_DATA_DIR = Path.home() / ".mcpforwork"


def data_dir() -> Path:
    """The directory holding the self-host SQLite database and assets."""
    return Path(os.environ.get("MCPFORWORK_DATA_DIR", str(_DEFAULT_DATA_DIR)))


def db_url() -> str:
    """The database URL. `MCPFORWORK_DB_URL` (sqlite:/// or postgres://) wins;
    otherwise the self-host SQLite file under `data_dir()`."""
    env = os.environ.get("MCPFORWORK_DB_URL")
    if env:
        return env
    return f"sqlite:///{data_dir() / 'mcpforwork.db'}"


_DEFAULT_LOCAL_EMAIL = "local@self-host"


def local_user_id() -> int | None:
    """The explicitly pinned tenant id for the self-host MCP server
    (`MCPFORWORK_USER_ID`), or None when unset — the server then resolves the
    local user by email instead (find-or-create, S6.8 tenant alignment).

    The hosted/parity API resolves identity from the magic-link session cookie
    instead; this helper is only for the local MCP process.
    """
    raw = os.environ.get("MCPFORWORK_USER_ID")
    return int(raw) if raw else None


def local_user_email() -> str:
    """The self-host local user's email (`MCPFORWORK_USER_EMAIL`, default
    `local@self-host`). The human logs into the dashboard with this same
    address so magic-link find-or-create resolves the SAME users row the MCP
    writes as (S6.8 tenant alignment, ADR 0006)."""
    return os.environ.get("MCPFORWORK_USER_EMAIL") or _DEFAULT_LOCAL_EMAIL


def post_login_redirect() -> str | None:
    """Where `GET /v1/auth/redeem` sends the browser after setting the session
    cookie (`MCPFORWORK_POST_LOGIN_REDIRECT` — fixed config, never
    client-controlled). Unset → the redeem route answers JSON 200."""
    return os.environ.get("MCPFORWORK_POST_LOGIN_REDIRECT") or None


def db_run_migrations() -> bool:
    """Whether request-path connections run migrations on connect. Default on
    (self-host SQLite ergonomics); set `MCPFORWORK_DB_RUN_MIGRATIONS=0` when
    connecting as the restricted Postgres `app` role, which cannot run DDL —
    migrations there are a deploy-time step for a privileged connection."""
    return os.environ.get("MCPFORWORK_DB_RUN_MIGRATIONS", "1") != "0"
