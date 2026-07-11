"""FastMCP stdio entrypoint — the self-host MCP server.

Thin: each tool opens a tenant-scoped UnitOfWork, calls a service, and returns
JSON with a next_action breadcrumb. No business logic, no browsing, no LLM.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcpforwork import config
from mcpforwork.adapters.db import SqlUnitOfWork, connect
from mcpforwork.domain.cv import MAX_CV_CHARS, extract_profile_from_cv
from mcpforwork.domain.profile import ProfileValidationError
from mcpforwork.entrypoints.mcp import guidance
from mcpforwork.entrypoints.mcp.guidance import SERVER_INSTRUCTIONS
from mcpforwork.services import apply as apply_service
from mcpforwork.services import (
    assets,
    audit,
    briefs,
    coverage,
    dedup,
    hunt,
    playbooks,
    profiles,
    review,
)

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


@contextmanager
def _tenant_uow() -> Iterator[tuple[SqlUnitOfWork, int]]:
    """The per-tool seam: a tenant-scoped UnitOfWork that always closes.
    Simplifier refactor (S4.4) over the repeated try/finally boilerplate."""
    uow, user_id = _uow()
    try:
        yield uow, user_id
    finally:
        uow.close()


@mcp.tool()
def report_playbook_result(source_slug: str, kind: str, diff: dict | None = None) -> str:
    """Opt-in crowd-learning: report what worked/moved/broke on a source
    (kind: success | drift | break) to improve the next pack version."""
    with _tenant_uow() as (uow, user_id):
        result = playbooks.report_playbook_result(uow, user_id, source_slug, kind, diff or {})
        if "error" in result:
            return _fail(result["error"])
        uow.commit()
    return _ok("report_playbook_result", result)


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
    with _tenant_uow() as (uow, user_id):
        prof = profiles.get_profile(uow, user_id, profile_id)
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
    with _tenant_uow() as (uow, user_id):
        rows = profiles.list_profiles(uow, user_id)
    return _ok("list_profiles", {"profiles": rows})


@mcp.tool()
def set_active_profile(profile_id: int) -> str:
    """Switch the active profile."""
    with _tenant_uow() as (uow, user_id):
        if profiles.get_profile(uow, user_id, profile_id) is None:
            return _fail(f"profile {profile_id} not found")
        profiles.set_active_profile(uow, user_id, profile_id)
        uow.commit()
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
    with _tenant_uow() as (uow, user_id):
        plan = hunt.hunt_plan(uow, user_id)
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
    with _tenant_uow() as (uow, user_id):
        result = hunt.submit_findings(uow, user_id, source_slug, findings)
        if "error" in result:
            return _fail(result["error"])
        uow.commit()
    return _ok("submit_findings", result)


@mcp.tool()
def check_seen(urls: list[str]) -> str:
    """Report which URLs the copilot already knows (scouted or applied). Only
    browse/apply the ones marked 'new'."""
    with _tenant_uow() as (uow, user_id):
        result = dedup.check_seen(uow, user_id, urls)
    return _ok("check_seen", result)


@mcp.tool()
def list_matches(min_score: int = 0, status: str | None = None, limit: int = 50) -> str:
    """The scouted matches, best score first."""
    with _tenant_uow() as (uow, user_id):
        matches = hunt.list_matches(uow, user_id, min_score=min_score, status=status, limit=limit)
    return _ok("list_matches", {"count": len(matches), "matches": matches})


@mcp.tool()
def get_match(finding_id: int) -> str:
    """Inspect one scouted match by id."""
    with _tenant_uow() as (uow, user_id):
        match = hunt.get_match(uow, user_id, finding_id)
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
    with _tenant_uow() as (uow, user_id):
        brief = briefs.get_generation_brief(uow, user_id, finding_id, asset_type)
    if "error" in brief:
        return _fail(brief["error"])
    return _ok("get_generation_brief", brief)


@mcp.tool()
def submit_asset(finding_id: int, asset_type: str, content: str) -> str:
    """Store YOUR draft (markdown) for a match; versions auto-increment."""
    with _tenant_uow() as (uow, user_id):
        result = assets.submit_asset(uow, user_id, finding_id, asset_type, content)
        if "error" in result:
            return _fail(result["error"])
        uow.commit()
    return _ok("submit_asset", result)


@mcp.tool()
def get_assets(finding_id: int, asset_type: str | None = None) -> str:
    """The stored drafts for a match, newest version first."""
    with _tenant_uow() as (uow, user_id):
        rows = assets.get_assets(uow, user_id, finding_id, asset_type)
    return _ok("get_assets", {"count": len(rows), "assets": rows})


@mcp.tool()
def ats_coverage_check(finding_id: int, asset_id: int) -> str:
    """Deterministic check of the posting's keywords vs a stored draft:
    covered / missing_but_have (truthfully addable) / genuine_gaps (acknowledge,
    never stuff)."""
    with _tenant_uow() as (uow, user_id):
        result = coverage.ats_coverage_check(uow, user_id, finding_id, asset_id)
    if "error" in result:
        return _fail(result["error"])
    return _ok("ats_coverage_check", result)


@mcp.tool()
def approve_match(finding_id: int) -> str:
    """Approve a match (human decision) so materials/apply can proceed."""
    with _tenant_uow() as (uow, user_id):
        result = review.approve_match(uow, user_id, finding_id)
        if "error" in result:
            return _fail(result["error"])
        uow.commit()
    return _ok("approve_match", result)


@mcp.tool()
def discard_match(finding_id: int, reason: str = "") -> str:
    """Discard a match (human decision); it will never be re-surfaced."""
    with _tenant_uow() as (uow, user_id):
        result = review.discard_match(uow, user_id, finding_id, reason)
        if "error" in result:
            return _fail(result["error"])
        uow.commit()
    return _ok("discard_match", result)


@mcp.tool()
def start_application(finding_id: int) -> str:
    """Start a supervised application session for an APPROVED match: runs the
    preflight (dedup gate, daily cap) and returns the step plan YOU execute in
    the user's browser. The plan never contains a submit step — request_submit
    is the only submission route and the human decides."""
    with _tenant_uow() as (uow, user_id):
        session = apply_service.start_application(uow, user_id, finding_id)
        if "error" in session:
            return _fail(session["error"])
        uow.commit()
    return _ok("start_application", session)


@mcp.tool()
def report_apply_progress(
    application_id: int, step_id: int, status: str, observed: str = "", obstacle: str = ""
) -> str:
    """Report a step's outcome (ok | blocked | mismatch). The server answers
    with the next step, a repair, or a human-pause — never a submit."""
    with _tenant_uow() as (uow, user_id):
        result = apply_service.report_apply_progress(
            uow, user_id, application_id, step_id, status, observed, obstacle
        )
        if "error" in result:
            return _fail(result["error"])
        uow.commit()
    return _ok("report_apply_progress", result)


@mcp.tool()
def resolve_field(
    application_id: int, field_label: str, field_type: str = "", options: list[str] | None = None
) -> str:
    """Deterministic answer for an unpredicted form question — from the profile
    or saved answers; otherwise ask_user (never invent)."""
    with _tenant_uow() as (uow, user_id):
        result = apply_service.resolve_field(
            uow, user_id, application_id, field_label, field_type, options
        )
    if "error" in result:
        return _fail(result["error"])
    return _ok("resolve_field", result)


@mcp.tool()
def save_form_answer(field_label: str, answer: str) -> str:
    """Persist a HUMAN-confirmed screener answer so it is never asked twice."""
    with _tenant_uow() as (uow, user_id):
        result = apply_service.save_form_answer(uow, user_id, field_label, answer)
        if "error" in result:
            return _fail(result["error"])
        uow.commit()
    return _ok("save_form_answer", result)


@mcp.tool()
def request_submit(application_id: int, summary: str = "") -> str:
    """THE consent gate. Ask permission to move to submission: at consent level
    0 the answer is always await_human — show the filled form; the HUMAN clicks
    Submit."""
    with _tenant_uow() as (uow, user_id):
        result = apply_service.request_submit(uow, user_id, application_id, summary)
        if "error" in result:
            return _fail(result["error"])
        uow.commit()
    return _ok("request_submit", result)


@mcp.tool()
def confirm_submitted(application_id: int, evidence: str = "") -> str:
    """AFTER the human confirms they clicked Submit: close the loop (state,
    dedup record, audit)."""
    with _tenant_uow() as (uow, user_id):
        result = apply_service.confirm_submitted(uow, user_id, application_id, evidence)
        if "error" in result:
            return _fail(result["error"])
        uow.commit()
    return _ok("confirm_submitted", result)


@mcp.tool()
def record_outcome(application_id: int, outcome: str, notes: str = "") -> str:
    """Record what happened (no_reply|rejected|interview|offer|hired) — feeds
    calibration."""
    with _tenant_uow() as (uow, user_id):
        result = apply_service.record_outcome(uow, user_id, application_id, outcome, notes)
        if "error" in result:
            return _fail(result["error"])
        uow.commit()
    return _ok("record_outcome", result)


@mcp.tool()
def get_asset_file(asset_id: int) -> str:
    """A local file path for the asset (for form uploads)."""
    with _tenant_uow() as (uow, user_id):
        result = apply_service.get_asset_file(uow, user_id, asset_id)
    if "error" in result:
        return _fail(result["error"])
    return _ok("get_asset_file", result)


@mcp.tool()
def record_application(url: str, channel: str = "", method: str = "", notes: str = "") -> str:
    """Record that the HUMAN submitted an application (any channel) so the
    copilot never re-surfaces the posting. Idempotent per URL."""
    with _tenant_uow() as (uow, user_id):
        result = dedup.record_application(
            uow, user_id, url=url, channel=channel, method=method, notes=notes
        )
        if "error" in result:
            return _fail(result["error"])
        uow.commit()
    return _ok("record_application", result)


@mcp.tool()
def profile_gaps() -> str:
    """What the profile is still missing (required first, then progressive).
    Offer ONE gap at a time when contextually useful — never a form-wall."""
    with _tenant_uow() as (uow, user_id):
        gaps = profiles.profile_gaps(uow, user_id)
    return _ok("profile_gaps", {"count": len(gaps), "gaps": gaps})


@mcp.tool()
def parse_cv(cv_text: str) -> str:
    """Zero-LLM regex extraction of contact fields from pasted CV text. Returns
    candidate fields (None = unknown — ask the human, never invent). Does NOT
    write the profile: CONFIRM with the human, then call update_profile."""
    if len(cv_text) > MAX_CV_CHARS:
        return _fail(f"cv_text too large (max {MAX_CV_CHARS} chars)")
    return _ok("parse_cv", extract_profile_from_cv(cv_text))


@mcp.prompt(name="setup")
def setup_session() -> str:
    """The /setup interview: build the Tier-1 profile in under 3 minutes."""
    return (
        "Interview the user to build their profile (target < 3 minutes):\n"
        "1. Ask for: name+email, country+city, work-authorization countries (+ "
        "sponsorship y/n), 1-5 target job titles + sector(s), seniority, employment "
        "types, work modes (+ relocation), minimum salary (PRIVATE - never disclosed "
        "in materials), languages, and their CV (paste text or a LinkedIn URL).\n"
        "2. Persist with update_profile (one call with the whole patch). For a "
        "LinkedIn/GitHub/portfolio URL: open it in the user's browser, extract "
        "structured fields, and call import_from_url_findings(url, fields).\n"
        "3. For pasted CV text call parse_cv first (zero-LLM extraction), CONFIRM "
        "the fields with the user, then persist.\n"
        "4. Offer Tier 2 progressively: call profile_gaps and raise ONE gap at a "
        "time when contextually useful (add_achievements is the highest-leverage "
        "input; set_style_profile captures the voice). Never a form-wall.\n"
        "Never invent values; only persist what the user actually said."
    )


@mcp.prompt(name="review")
def review_session() -> str:
    """The /review loop: triage scouted matches with the human."""
    return (
        "Review the pipeline with the user:\n"
        "1. list_matches(min_score=40) and present them best-first (title, company, "
        "score, why it scored - the breakdown).\n"
        "2. For each, the HUMAN decides: approve_match(id) or discard_match(id, "
        "reason). Never approve or discard on your own judgment.\n"
        "3. For approved matches, offer /apply (draft materials)."
    )


@mcp.prompt(name="apply")
def apply_session() -> str:
    """The /apply flow (S3 scope): brief -> honest draft -> coverage -> human sends."""
    return (
        "Draft application materials for an approved match:\n"
        "1. get_generation_brief(finding_id, asset_type) - cv or cover_letter.\n"
        "2. Draft honoring honesty_rules: ONLY claims the facts_inventory proves; "
        "acknowledge gaps; match the posting's language; use the style sample.\n"
        "3. submit_asset(finding_id, asset_type, content), then "
        "ats_coverage_check(finding_id, asset_id).\n"
        "4. Add missing_but_have items truthfully; NEVER stuff genuine_gaps - "
        "acknowledge them. Iterate once if coverage is weak.\n"
        "5. Show the final draft to the human. THE HUMAN sends/submits it - never "
        "auto-submit anything (browser apply orchestration arrives in a later "
        "version; record_application(url, channel) after the human confirms)."
    )


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
