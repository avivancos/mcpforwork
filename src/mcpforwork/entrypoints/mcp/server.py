"""FastMCP stdio entrypoint — the self-host MCP server.

Thin: each tool opens a tenant-scoped UnitOfWork, calls a service, and returns
JSON with a next_action breadcrumb. No business logic, no browsing, no LLM.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import sys

from mcp.server.fastmcp import FastMCP

from mcpforwork import config
from mcpforwork.adapters.db import SqlUnitOfWork, connect
from mcpforwork.entrypoints.mcp import guidance
from mcpforwork.entrypoints.mcp.guidance import SERVER_INSTRUCTIONS

mcp = FastMCP("mcpforwork", instructions=SERVER_INSTRUCTIONS)

INVARIANTS = [
    "Zero server-side LLM — the client LLM is the only model.",
    "The server never browses, fetches, or scrapes; the client's browser does.",
    "Never auto-submit — the human reviews and submits (consent gate).",
]


def _ensure_local_user(uow: SqlUnitOfWork, user_id: int) -> None:
    """Self-host convenience: guarantee the tenant's users row exists so
    per-user FKs resolve. Idempotent."""
    if uow.fetchone("SELECT id FROM users WHERE id = ?", (user_id,)) is None:
        uow.execute("INSERT INTO users (id, email) VALUES (?, ?)", (user_id, "local@self-host"))
        uow.commit()


def _uow() -> tuple[SqlUnitOfWork, int]:
    """Open a migrated, tenant-scoped UnitOfWork for the self-host user."""
    uow = connect(config.db_url())
    user_id = config.local_user_id()
    _ensure_local_user(uow, user_id)
    uow.set_user_context(user_id)
    return uow, user_id


def _tool_names() -> list[str]:
    return sorted(t.name for t in mcp._tool_manager.list_tools())


@mcp.tool()
def server_info() -> str:
    """Version + capability handshake: server version, registered tools, and the
    load-bearing invariants the client must respect."""
    try:
        version = importlib.metadata.version("mcpforwork")
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        version = "unknown"
    return json.dumps(
        {
            "name": "mcpforwork",
            "version": version,
            "tools": _tool_names(),
            "invariants": INVARIANTS,
            "next_action": guidance.next_action("server_info"),
        }
    )


def main() -> None:
    mcp.run(transport=os.environ.get("MCPFORWORK_TRANSPORT", "stdio"))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
