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


def local_user_id() -> int:
    """The tenant id for the self-host stdio MCP server.

    The hosted/parity API resolves identity from the magic-link session cookie
    instead; this helper is only for the local MCP process.
    """
    return int(os.environ.get("MCPFORWORK_USER_ID", "1"))
