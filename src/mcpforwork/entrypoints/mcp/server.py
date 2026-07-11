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
from mcpforwork.domain.profile import ProfileValidationError
from mcpforwork.entrypoints.mcp import guidance
from mcpforwork.entrypoints.mcp.guidance import SERVER_INSTRUCTIONS
from mcpforwork.services import audit, profiles

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


def _fail(message: str) -> str:
    return json.dumps({"error": message})


def _ok(tool: str, payload: dict) -> str:
    payload["next_action"] = guidance.next_action(tool)
    return json.dumps(payload)


def _active_pid(uow: SqlUnitOfWork, user_id: int) -> int | None:
    active = profiles.get_profile(uow, user_id)
    return active["id"] if active else None


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


@mcp.tool()
def create_profile(patch: dict | None = None, label: str = "default") -> str:
    """Create a new profile (made active) and return it. `patch` is the intake
    fields (name, titles, sectors, work mode, …)."""
    uow, user_id = _uow()
    try:
        pid = profiles.create_profile(uow, user_id, patch or {}, label=label)
        uow.commit()
        prof = profiles.get_profile(uow, user_id, pid)
    except ProfileValidationError as exc:
        return _fail(str(exc))
    finally:
        uow.close()
    return _ok("create_profile", {"ok": True, "profile_id": pid, "profile": prof})


@mcp.tool()
def get_profile(profile_id: int | None = None) -> str:
    """Return the active profile (or a given one), JSON fields parsed."""
    uow, user_id = _uow()
    try:
        prof = profiles.get_profile(uow, user_id, profile_id)
    finally:
        uow.close()
    if prof is None:
        return _fail("no profile yet — call update_profile to create one")
    return _ok("get_profile", {"profile": prof})


@mcp.tool()
def update_profile(patch: dict, profile_id: int | None = None) -> str:
    """Apply a partial update. With no profile_id, updates the active profile —
    or creates it if the user has none yet (the /setup path)."""
    uow, user_id = _uow()
    try:
        if profile_id is None:
            active = profiles.get_profile(uow, user_id)
            if active is None:
                pid = profiles.create_profile(uow, user_id, patch)
            else:
                pid = active["id"]
                profiles.update_profile(uow, user_id, pid, patch)
        else:
            profiles.update_profile(uow, user_id, profile_id, patch)
            pid = profile_id
        uow.commit()
        prof = profiles.get_profile(uow, user_id, pid)
    except ProfileValidationError as exc:
        return _fail(str(exc))
    finally:
        uow.close()
    return _ok("update_profile", {"ok": True, "profile_id": pid, "profile": prof})


@mcp.tool()
def list_profiles() -> str:
    """List the user's profiles (the active one has is_active=1)."""
    uow, user_id = _uow()
    try:
        rows = profiles.list_profiles(uow, user_id)
    finally:
        uow.close()
    return _ok("list_profiles", {"profiles": rows})


@mcp.tool()
def set_active_profile(profile_id: int) -> str:
    """Switch the active profile."""
    uow, user_id = _uow()
    try:
        if profiles.get_profile(uow, user_id, profile_id) is None:
            return _fail(f"profile {profile_id} not found")
        profiles.set_active_profile(uow, user_id, profile_id)
        uow.commit()
    finally:
        uow.close()
    return _ok("set_active_profile", {"ok": True, "active_profile_id": profile_id})


@mcp.tool()
def add_achievements(items: list[dict], profile_id: int | None = None) -> str:
    """Append quantified wins (each needs a `metric`) to the achievements bank."""
    uow, user_id = _uow()
    try:
        pid = profile_id if profile_id is not None else _active_pid(uow, user_id)
        if pid is None:
            return _fail("no profile — create one first")
        ids = profiles.add_achievements(uow, user_id, pid, items)
        uow.commit()
    except ProfileValidationError as exc:
        return _fail(str(exc))
    finally:
        uow.close()
    return _ok("add_achievements", {"ok": True, "achievement_ids": ids})


@mcp.tool()
def set_style_profile(
    writing_sample: str, directives: dict | None = None, profile_id: int | None = None
) -> str:
    """Capture the user's writing voice so drafts sound like them."""
    uow, user_id = _uow()
    try:
        pid = profile_id if profile_id is not None else _active_pid(uow, user_id)
        if pid is None:
            return _fail("no profile — create one first")
        profiles.set_style_profile(uow, user_id, pid, writing_sample, directives)
        uow.commit()
    except ProfileValidationError as exc:
        return _fail(str(exc))
    finally:
        uow.close()
    return _ok("set_style_profile", {"ok": True, "profile_id": pid})


@mcp.tool()
def import_from_url_findings(url: str, fields: dict) -> str:
    """Apply client-LLM-extracted structured fields (LinkedIn/GitHub/portfolio)
    to the active profile, recording the source url for provenance."""
    uow, user_id = _uow()
    try:
        active = profiles.get_profile(uow, user_id)
        if active is None:
            pid = profiles.create_profile(uow, user_id, fields)
        else:
            pid = active["id"]
            profiles.update_profile(uow, user_id, pid, fields)
        audit.record(uow, user_id, "import_from_url_findings", {"url": url})
        uow.commit()
        prof = profiles.get_profile(uow, user_id, pid)
    except ProfileValidationError as exc:
        return _fail(str(exc))
    finally:
        uow.close()
    return _ok(
        "import_from_url_findings",
        {"ok": True, "profile_id": pid, "profile": prof, "source": url},
    )


def main() -> None:
    mcp.run(transport=os.environ.get("MCPFORWORK_TRANSPORT", "stdio"))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
