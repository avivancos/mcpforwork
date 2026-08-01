"""Pipeline reads — compose findings + applications + assets + audit into the
dashboard contract (`web/src/lib/api/types.ts`).

One service, two thin wrappers: the Starlette parity API and the
`pipeline_stats` MCP tool. ISO-8601 timestamps and string ids; the web
humanizes at render. Read-only — the caller owns the transaction.

`audit_log` is NOT RLS-forced (ADR 0001 ledger): every audit read here filters
`user_id` explicitly. That filter is the tenant wall and is covered by a
live-Postgres parity test.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from mcpforwork.ports.db import Row, UnitOfWork
from mcpforwork.services import hunt

# Web stage vocabulary (types.ts Stage) ← application outcomes (services/apply
# OUTCOMES). `hired` renders as `offer` — the web has no hired chip yet.
_OUTCOME_STAGES = {
    "no_reply": "no_response",
    "rejected": "rejected",
    "interview": "interview",
    "offer": "offer",
    "hired": "offer",
}

# Why an awaiting_you item is paused, per application state.
_NEEDS_YOU = {
    "awaiting_human": "Form filled — review it and submit",
    "submit_requested": "Confirm the submission landed",
}

# Stages counting as "reached the employer" / "got a response".
_SUBMITTED_STAGES = frozenset(
    {"submitted", "verified", "interview", "offer", "rejected", "no_response"}
)
_RESPONSE_STAGES = frozenset({"rejected", "interview", "offer"})
_INTERVIEW_STAGES = frozenset({"interview", "offer"})


def derive_stage(finding_status: str, application: Mapping[str, Any] | None) -> str:
    """The dashboard stage for a (finding, latest application) pair. Pure."""
    if finding_status == "discarded":
        return "discarded"
    if application is not None:
        outcome = application.get("outcome")
        if outcome:
            return _OUTCOME_STAGES.get(outcome, "submitted")
        state = application.get("state")
        if state in ("awaiting_human", "submit_requested"):
            return "awaiting_you"
        if state in ("draft", "filling"):
            return "filling"
        if state == "submitted":
            return "submitted"
        if state == "verified":
            return "verified"
        # abandoned: the match falls back to new_match below
    return "new_match"


def _latest_applications(uow: UnitOfWork, user_id: int) -> dict[int, Row]:
    """finding_id → newest application row (one query, both dialects)."""
    rows = uow.fetchall(
        "SELECT a.* FROM applications a JOIN ("
        "  SELECT finding_id, MAX(id) AS mid FROM applications"
        "  WHERE user_id = ? GROUP BY finding_id"
        " ) latest ON a.id = latest.mid",
        (user_id,),
    )
    return {row["finding_id"]: row for row in rows}


def _item(finding: Mapping[str, Any], app: Mapping[str, Any] | None) -> dict[str, Any]:
    stage = derive_stage(finding["status"], app)
    active = app is not None and app["state"] != "abandoned"
    item: dict[str, Any] = {
        "id": str(finding["id"]),
        "fit": finding["score"] or 0,
        "role": finding["title"],
        "company": finding.get("company_name") or "",
        "city": finding.get("location") or "",
        "stage": stage,
        "consent": "supervised" if active else None,
        "updated": app["updated_at"] if active else finding["last_seen"],
    }
    if stage == "awaiting_you":
        item["needsYou"] = _NEEDS_YOU.get(app["state"], "Needs your input")
    return item


def _pairs(uow: UnitOfWork, user_id: int, limit: int) -> list[tuple[Row, Row | None]]:
    findings = uow.fetchall(
        "SELECT * FROM explore_findings WHERE user_id = ? ORDER BY score DESC, id DESC LIMIT ?",
        (user_id, limit),
    )
    by_finding = _latest_applications(uow, user_id)
    return [(f, by_finding.get(f["id"])) for f in findings]


def list_pipeline(uow: UnitOfWork, user_id: int, limit: int = 200) -> list[dict[str, Any]]:
    """PipelineItem[] — every finding, best score first."""
    return [_item(f, app) for f, app in _pairs(uow, user_id, limit)]


def _as_dt(value: Any) -> datetime:
    """SQLite stores ISO text; Postgres returns datetimes. Normalize to an
    aware UTC datetime for comparison."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def pipeline_stats(uow: UnitOfWork, user_id: int, *, now: datetime | None = None) -> dict[str, Any]:
    """PipelineStats — counts over the derived stages. `now` is injectable."""
    now = now or datetime.now(UTC)
    pairs = _pairs(uow, user_id, limit=1000)
    stages = [derive_stage(f["status"], app) for f, app in pairs]
    week_start = now - timedelta(days=7)
    new_this_week = sum(
        1
        for (f, _), stage in zip(pairs, stages, strict=True)
        if stage == "new_match" and _as_dt(f["first_seen"]) >= week_start
    )
    submitted = [s for s in stages if s in _SUBMITTED_STAGES]
    return {
        "newMatches": {
            "count": stages.count("new_match"),
            "foundThisWeek": new_this_week,
        },
        "needsYou": {"count": stages.count("awaiting_you")},
        "submitted": {
            "count": len(submitted),
            "verified": stages.count("verified"),
        },
        "responses": {
            "count": sum(1 for s in stages if s in _RESPONSE_STAGES),
            "of": len(submitted),
            "interviews": sum(1 for s in stages if s in _INTERVIEW_STAGES),
        },
    }


def get_match_detail(uow: UnitOfWork, user_id: int, finding_id: int) -> dict[str, Any] | None:
    """MatchDetail for the web's getOrNull — None when the finding is not the
    caller's (cross-tenant reads are indistinguishable from missing)."""
    finding = hunt.get_match(uow, user_id, finding_id)
    if finding is None:
        return None
    app = uow.fetchone(
        "SELECT * FROM applications WHERE user_id = ? AND finding_id = ? ORDER BY id DESC LIMIT 1",
        (user_id, finding_id),
    )
    asset_rows = uow.fetchall(
        "SELECT id, asset_type, version, created_at FROM generated_assets"
        " WHERE user_id = ? AND finding_id = ? ORDER BY id DESC",
        (user_id, finding_id),
    )
    # audit_log is not RLS-forced — this explicit user_id filter is the wall.
    audit_rows = uow.fetchall(
        "SELECT action, detail, created_at FROM audit_log"
        " WHERE user_id = ? ORDER BY id DESC LIMIT 200",
        (user_id,),
    )

    breakdown = finding.get("score_breakdown") or {}
    detail: dict[str, Any] = {
        **_item(finding, app),
        "pack": finding["source_slug"],
        "employmentType": "",  # not stored on findings — never fabricated
        "postingUrl": finding["url"],
        "constraintChecks": [
            {"label": label, "ok": points > 0} for label, points in breakdown.items()
        ],
        "dedup": f"hash {finding['dedup_hash'][:12]} · first seen {finding['first_seen']}",
        "assets": [
            {
                "id": str(a["id"]),
                "name": f"{a['asset_type']} v{a['version']}",
                "kind": "resume" if a["asset_type"] == "cv" else "cover",
                "note": str(a["created_at"]),
            }
            for a in asset_rows
        ],
        "audit": _finding_audit(audit_rows, finding_id, app["id"] if app else None),
    }
    return detail


def _finding_audit(
    audit_rows: list[Row], finding_id: int, application_id: int | None
) -> list[dict[str, Any]]:
    """Audit entries touching this finding/application, newest first."""
    events = []
    for row in audit_rows:
        try:
            detail = json.loads(row["detail"] or "{}")
        except (TypeError, ValueError):
            detail = {}
        if detail.get("finding_id") != finding_id and (
            application_id is None or detail.get("application_id") != application_id
        ):
            continue
        event = row["action"]
        if detail.get("summary"):
            event = f"{event} — {detail['summary']}"
        events.append({"at": str(row["created_at"]), "event": event})
    return events
