"""Browser-apply orchestration: the server choreographs, the client's browser acts.

start_application runs the deterministic preflight and persists the session.
Consent is structural: the step plan never contains a submit step; only
request_submit (S4.3) routes submission, and at L0 it always awaits the human.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from mcpforwork.domain.apply_flow import build_steps
from mcpforwork.domain.dedup import dedup_hash
from mcpforwork.packs import registry
from mcpforwork.ports.db import UnitOfWork
from mcpforwork.services import assets as assets_service
from mcpforwork.services import audit, hunt, profiles

MAX_APPLICATIONS_PER_DAY = 10

_OPEN_STATES = ("draft", "filling", "awaiting_human")


def _today_started_count(uow: UnitOfWork, user_id: int) -> int:
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    row = uow.fetchone(
        "SELECT COUNT(*) AS n FROM applications WHERE user_id = ? AND created_at >= ?",
        (user_id, day),
    )
    return row["n"]


def start_application(uow: UnitOfWork, user_id: int, finding_id: int) -> dict[str, Any]:
    """Deterministic preflight → persisted application session with a step plan."""
    match = hunt.get_match(uow, user_id, finding_id)
    if match is None:
        return {"error": f"match {finding_id} not found"}
    if match["status"] != "approved":
        return {"error": f"match {finding_id} is '{match['status']}' — approve it first (/review)"}

    # Idempotent re-open: one open application per finding.
    placeholders = ", ".join(["?"] * len(_OPEN_STATES))
    open_row = uow.fetchone(
        f"SELECT id, state, steps, consent_level FROM applications"
        f" WHERE user_id = ? AND finding_id = ? AND state IN ({placeholders})",
        (user_id, finding_id, *_OPEN_STATES),
    )
    if open_row is not None:
        return {
            "application_id": open_row["id"],
            "state": open_row["state"],
            "consent_level": open_row["consent_level"],
            "steps": json.loads(open_row["steps"] or "[]"),
            "reopened": True,
        }

    # Dedup gate: never apply twice.
    digest = dedup_hash(match["url"])
    if uow.fetchone(
        "SELECT id FROM external_applications WHERE dedup_hash = ? AND user_id = ?",
        (digest, user_id),
    ):
        return {"error": "already applied to this posting (dedup gate)"}

    # Daily cap protects application quality and the user's reputation.
    if _today_started_count(uow, user_id) >= MAX_APPLICATIONS_PER_DAY:
        return {"error": f"daily cap reached ({MAX_APPLICATIONS_PER_DAY}/day)"}

    profile = profiles.get_profile(uow, user_id)
    if profile is None:
        return {"error": "no active profile — run /setup first"}
    asset_rows = assets_service.get_assets(uow, user_id, finding_id)
    playbook = registry.load_sources().get(match["source_slug"])
    apply_playbook = playbook.apply if playbook else {}

    steps = build_steps(match, profile, asset_rows, apply_playbook)
    app_id = uow.insert(
        "INSERT INTO applications (user_id, finding_id, state, apply_method, steps)"
        " VALUES (?, ?, 'filling', ?, ?)",
        (user_id, finding_id, apply_playbook.get("ats_hint"), json.dumps(steps)),
    )
    audit.record(
        uow, user_id, "start_application", {"application_id": app_id, "finding_id": finding_id}
    )
    return {
        "application_id": app_id,
        "state": "filling",
        "consent_level": 0,
        "steps": steps,
        "warnings": []
        if asset_rows
        else ["no drafted assets for this match — consider /apply first"],
    }
