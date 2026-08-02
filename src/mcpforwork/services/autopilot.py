"""Autopilot consent artifacts (S7.2a L1 + S7.2b L2, ADR 0005).

THE write side of consent: approval artifacts and autopilot policies are
written exclusively here, behind the human-session HTTP API. The MCP
entrypoint never calls the write functions — no sequence of agent tool calls
(possibly prompt-injected by posting content) can mint consent. Reads stay in
services/apply.py, which evaluates the recorded artifacts inside
request_submit (decision order: L1 approval -> L2 policy -> await_human).
"""

from __future__ import annotations

from typing import Any

from mcpforwork.domain.dedup import dedup_hash
from mcpforwork.packs import registry
from mcpforwork.ports.db import UnitOfWork
from mcpforwork.services import audit
from mcpforwork.services.clock import utcnow_iso

# Approval is meaningful exactly while the human is being asked: the two
# states the dashboard derives as "awaiting you".
_APPROVABLE_STATES = ("awaiting_human", "submit_requested")

# Policy bounds (S7.2b): a cap above 50/day is spam, not autopilot; the floor
# keeps the artifact meaningful (a 0-cap policy would authorize nothing).
_MIN_SCORE_RANGE = (0, 100)
_MAX_PER_DAY_RANGE = (1, 50)


def approve_submit(
    uow: UnitOfWork, user_id: int, application_id: int, via: str = "dashboard"
) -> dict[str, Any]:
    """Record the human's approval to submit one application, once.

    State-guarded to the "awaiting you" stage; cross-tenant applications are
    indistinguishable from unknown ones (not_found)."""
    row = uow.fetchone(
        "SELECT state, submit_approved_at FROM applications WHERE id = ? AND user_id = ?",
        (application_id, user_id),
    )
    if row is None:
        return {"error": f"application {application_id} not found", "kind": "not_found"}
    if row["state"] not in _APPROVABLE_STATES:
        return {
            "error": f"application is '{row['state']}' — only an application waiting on "
            "you can be approved",
            "kind": "invalid_state",
        }
    if row["submit_approved_at"] is not None:
        return {"ok": True, "already_approved": True}
    now = utcnow_iso()
    uow.execute(
        "UPDATE applications SET submit_approved_at = ?, submit_approved_via = ?,"
        " updated_at = ? WHERE id = ? AND user_id = ?",
        (now, via, now, application_id, user_id),
    )
    audit.record(
        uow,
        user_id,
        "approve_submit",
        {"application_id": application_id, "via": via, "approved_at": now},
    )
    return {"ok": True}


# --------------------------------------------------------------------------- #
# L2: the recorded autopilot policy (S7.2b)
# --------------------------------------------------------------------------- #


def put_policy(
    uow: UnitOfWork, user_id: int, *, min_score: int, max_per_day: int
) -> dict[str, Any]:
    """Record a new autopilot policy (append-only): the prior active row is
    revoked in the same transaction, so at most one policy is active and the
    history of every change survives for the audit trail."""
    # isinstance(True, int) is True in Python — JSON booleans must NOT pass as
    # integers (SQLite would store 1; psycopg would 500 against the INT column).
    if (
        not isinstance(min_score, int)
        or isinstance(min_score, bool)
        or not _MIN_SCORE_RANGE[0] <= min_score <= _MIN_SCORE_RANGE[1]
    ):
        return {
            "error": f"min_score must be an integer {_MIN_SCORE_RANGE[0]}–{_MIN_SCORE_RANGE[1]}",
            "kind": "invalid_input",
        }
    if (
        not isinstance(max_per_day, int)
        or isinstance(max_per_day, bool)
        or not _MAX_PER_DAY_RANGE[0] <= max_per_day <= _MAX_PER_DAY_RANGE[1]
    ):
        lo, hi = _MAX_PER_DAY_RANGE
        return {"error": f"max_per_day must be an integer {lo}–{hi}", "kind": "invalid_input"}
    now = utcnow_iso()
    uow.execute(
        "UPDATE autopilot_policy SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (now, user_id),
    )
    policy_id = uow.insert(
        "INSERT INTO autopilot_policy (user_id, enabled, min_score, max_per_day, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        # Bound as a real bool: psycopg needs it for the BOOLEAN column;
        # sqlite3 adapts True -> 1 for the INTEGER column.
        (user_id, True, min_score, max_per_day, now),
    )
    audit.record(
        uow,
        user_id,
        "put_autopilot_policy",
        {"policy_id": policy_id, "min_score": min_score, "max_per_day": max_per_day},
    )
    return {"ok": True, "policy_id": policy_id}


def get_policy(uow: UnitOfWork, user_id: int) -> dict[str, Any] | None:
    """The active policy: newest non-revoked row. None = autopilot off."""
    return uow.fetchone(
        "SELECT id, enabled, min_score, max_per_day, created_at, revoked_at"
        " FROM autopilot_policy WHERE user_id = ? AND revoked_at IS NULL"
        " ORDER BY id DESC LIMIT 1",
        (user_id,),
    )


def revoke_policy(uow: UnitOfWork, user_id: int) -> dict[str, Any]:
    """Revoke the active policy. The row stays as history; new request_submit
    calls fall back to await_human. Already-minted authorizations are NOT
    recalled (an agent mid-submit on one is not stranded)."""
    policy = get_policy(uow, user_id)
    if policy is None:
        return {"error": "no active autopilot policy", "kind": "not_found"}
    now = utcnow_iso()
    uow.execute(
        "UPDATE autopilot_policy SET revoked_at = ? WHERE id = ? AND user_id = ?",
        (now, policy["id"], user_id),
    )
    audit.record(uow, user_id, "revoke_autopilot_policy", {"policy_id": policy["id"]})
    return {"ok": True}


def safe_source_slugs() -> frozenset[str]:
    """Sources whose pack flags them auto_apply_safe (S7.2c curates which —
    human browser verification required). Until then, honestly empty."""
    return frozenset(
        slug for slug, src in registry.load_sources().items() if src.apply.get("auto_apply_safe")
    )


def evaluate(
    *,
    policy: dict[str, Any] | None,
    score: int,
    source_slug: str,
    safe_sources: frozenset[str] | set[str],
    authorized_today: int,
) -> dict[str, Any]:
    """PURE L2 decision: authorize only when every criterion holds. The
    criteria snapshot is what the authorization audit row carries — the record
    proves WHICH policy/score/source/cap state produced the decision."""
    snapshot = {
        "policy_id": policy["id"] if policy else None,
        "score": score,
        "source_slug": source_slug,
        "cap_used": authorized_today,
    }
    if policy is None or not policy["enabled"]:
        return {"authorize": False, "reason": "no active policy", "snapshot": snapshot}
    if source_slug not in safe_sources:
        return {"authorize": False, "reason": "source not auto_apply_safe", "snapshot": snapshot}
    if score < policy["min_score"]:
        return {
            "authorize": False,
            "reason": f"score {score} below policy min {policy['min_score']}",
            "snapshot": snapshot,
        }
    if authorized_today >= policy["max_per_day"]:
        return {"authorize": False, "reason": "daily cap reached", "snapshot": snapshot}
    snapshot["cap_used"] = authorized_today + 1  # this authorization included
    return {"authorize": True, "reason": "", "snapshot": snapshot}


def queue(
    uow: UnitOfWork,
    user_id: int,
    *,
    safe_sources: frozenset[str] | set[str] | None = None,
) -> dict[str, Any]:
    """The L2 work queue — a QUERY, not a table: approved matches on
    auto_apply_safe sources scoring at/above the policy min, not dedup-blocked,
    with no open application. Shared by the MCP tool and the dashboard."""
    policy = get_policy(uow, user_id)
    if policy is None:
        return {"policy": None, "items": []}
    safe = safe_sources if safe_sources is not None else safe_source_slugs()
    if not safe:
        return {"policy": policy, "items": []}
    placeholders = ", ".join(["?"] * len(safe))
    rows = uow.fetchall(
        f"SELECT f.id, f.title, f.company_name, f.location, f.score, f.source_slug,"
        f" f.url, f.last_seen FROM explore_findings f"
        f" WHERE f.user_id = ? AND f.status = 'approved' AND f.score >= ?"
        f" AND f.source_slug IN ({placeholders})"
        f" AND NOT EXISTS (SELECT 1 FROM applications a WHERE a.user_id = f.user_id"
        f" AND a.finding_id = f.id AND a.state IN ('draft', 'filling', 'awaiting_human',"
        f" 'submit_requested'))"
        f" ORDER BY f.score DESC, f.id",
        (user_id, policy["min_score"], *sorted(safe)),
    )
    seen = {
        r["dedup_hash"]
        for r in uow.fetchall(
            "SELECT dedup_hash FROM external_applications WHERE user_id = ?", (user_id,)
        )
    }
    items = []
    for row in rows:
        if dedup_hash(row["url"]) in seen:
            continue  # dedup-blocked: never resurface a posting already applied
        items.append(
            {
                "id": str(row["id"]),
                "role": row["title"],
                "company": row["company_name"] or "",
                "city": row["location"] or "",
                "fit": row["score"] or 0,
                "source": row["source_slug"],
                "url": row["url"],
                "updated": row["last_seen"],
            }
        )
    return {"policy": policy, "items": items}
