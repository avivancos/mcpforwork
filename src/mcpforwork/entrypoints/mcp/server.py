"""FastMCP stdio entrypoint — the self-host MCP server.

Thin: each tool opens a tenant-scoped UnitOfWork, calls a service, and returns
JSON with a next_action breadcrumb. No business logic, no browsing, no LLM.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import sys
from datetime import date, datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcpforwork import config
from mcpforwork.adapters.db import SqlUnitOfWork, connect
from mcpforwork.domain.profile import ProfileValidationError
from mcpforwork.entrypoints.mcp import guidance
from mcpforwork.entrypoints.mcp.guidance import SERVER_INSTRUCTIONS
from mcpforwork.services import audit, briefs, dedup, hunt, profiles

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
    try:
        user_id = config.local_user_id()
        _ensure_local_user(uow, user_id)
        uow.set_user_context(user_id)
    except BaseException:
        uow.close()  # never leak the connection if setup fails
        raise
    return uow, user_id


def _tool_names() -> list[str]:
    return sorted(t.name for t in mcp._tool_manager.list_tools())


def _json_default(obj: Any) -> str:
    """Serialize values json.dumps cannot — notably Postgres TIMESTAMP columns,
    which deserialize to datetime (SQLite returns ISO strings). Both dialects
    emit ISO-8601 strings, so tool payloads are dialect-neutral."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return str(obj)


def _fail(message: str) -> str:
    return json.dumps({"error": message})


def _ok(tool: str, payload: dict) -> str:
    payload["next_action"] = guidance.next_action(tool)
    return json.dumps(payload, default=_json_default)


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
        },
        default=_json_default,
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


# --------------------------------------------------------------------------- #
# Hunt tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def hunt_plan() -> str:
    """Per-source search playbooks for the active profile — the URLs YOU open in
    the user's browser to find postings."""
    uow, user_id = _uow()
    try:
        plan = hunt.hunt_plan(uow, user_id)
    finally:
        uow.close()
    if "error" in plan:
        return _fail(plan["error"])
    return _ok("hunt_plan", plan)


@mcp.tool()
def source_playbook(slug: str, query: str = "") -> str:
    """The full search + apply playbook for one source. Pack data only — no DB."""
    playbook = hunt.source_playbook(slug, query)
    if "error" in playbook:
        return _fail(playbook["error"])
    return _ok("source_playbook", playbook)


@mcp.tool()
def list_sources(countries: list[str] | None = None, sectors: list[str] | None = None) -> str:
    """List enabled sources, optionally filtered by country/sector tags. Pack
    data only — no DB."""
    sources = hunt.list_sources(countries, sectors)
    return _ok("list_sources", {"count": len(sources), "sources": sources})


@mcp.tool()
def submit_findings(source_slug: str, findings: list[dict]) -> str:
    """Ingest postings YOU extracted from a source: deduped, scored against the
    profile, and persisted. Each finding needs at least url + title."""
    uow, user_id = _uow()
    try:
        result = hunt.submit_findings(uow, user_id, source_slug, findings)
        if "error" in result:
            return _fail(result["error"])
        uow.commit()
    finally:
        uow.close()
    return _ok("submit_findings", result)


@mcp.tool()
def check_seen(urls: list[str]) -> str:
    """Report which URLs the copilot already knows (scouted or applied). Only
    browse/apply the ones marked 'new'."""
    uow, user_id = _uow()
    try:
        result = dedup.check_seen(uow, user_id, urls)
    finally:
        uow.close()
    return _ok("check_seen", result)


@mcp.tool()
def list_matches(min_score: int = 0, status: str | None = None, limit: int = 50) -> str:
    """The scouted matches, best score first."""
    uow, user_id = _uow()
    try:
        matches = hunt.list_matches(uow, user_id, min_score=min_score, status=status, limit=limit)
    finally:
        uow.close()
    return _ok("list_matches", {"count": len(matches), "matches": matches})


@mcp.tool()
def get_match(finding_id: int) -> str:
    """Inspect one scouted match by id."""
    uow, user_id = _uow()
    try:
        match = hunt.get_match(uow, user_id, finding_id)
    finally:
        uow.close()
    if match is None:
        return _fail(f"match {finding_id} not found")
    return _ok("get_match", {"match": match})


# --------------------------------------------------------------------------- #
# Asset tools
# --------------------------------------------------------------------------- #
@mcp.tool()
def get_generation_brief(finding_id: int, asset_type: str) -> str:
    """The structured brief (job keywords + facts inventory + style + honesty
    rules) YOU draft the cv/cover_letter from. Only claim what the
    facts_inventory proves."""
    uow, user_id = _uow()
    try:
        brief = briefs.get_generation_brief(uow, user_id, finding_id, asset_type)
    finally:
        uow.close()
    if "error" in brief:
        return _fail(brief["error"])
    return _ok("get_generation_brief", brief)


@mcp.prompt(name="hunt")
def hunt_session() -> str:
    """The /hunt playbook: turn the profile into searches, browse, ingest, review."""
    return (
        "Run a hunt for the active profile:\n"
        "1. Call hunt_plan to get per-source search URLs.\n"
        "2. For each source, open its search_url in the user's browser and extract "
        "the postings (url, title, company_name, location, remote_scope, salary_text, "
        "description).\n"
        "3. Before listing, you may call check_seen(urls) and skip any marked 'skip'.\n"
        "4. Call submit_findings(source_slug, findings) — the server dedups against "
        "what's already scouted/applied and scores each against the profile.\n"
        "5. Call list_matches(min_score=40) to review what scored well.\n"
        "Never fabricate postings; only submit what you actually saw. Never auto-apply."
    )


def main() -> None:
    mcp.run(transport=os.environ.get("MCPFORWORK_TRANSPORT", "stdio"))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
