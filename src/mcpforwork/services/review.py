"""Review use cases: approve / discard a scouted match (audited)."""

from __future__ import annotations

from typing import Any

from mcpforwork.ports.db import UnitOfWork
from mcpforwork.services import audit, hunt

# States a match can be approved from. Terminal states (discarded,
# applied_external) require an explicit human re-open, not a silent flip.
_APPROVABLE = frozenset({"new", "review"})


def approve_match(uow: UnitOfWork, user_id: int, finding_id: int) -> dict[str, Any]:
    match = hunt.get_match(uow, user_id, finding_id)
    if match is None:
        return {"error": f"match {finding_id} not found"}
    if match["status"] not in _APPROVABLE:
        return {"error": f"match {finding_id} is '{match['status']}' — cannot approve"}
    # State predicate in the UPDATE itself: a concurrent discard between the
    # read above and this write must not be silently overwritten.
    cur = uow.execute(
        "UPDATE explore_findings SET status = 'approved'"
        " WHERE id = ? AND user_id = ? AND status IN ('new', 'review')",
        (finding_id, user_id),
    )
    if cur.rowcount == 0:
        return {"error": f"match {finding_id} changed state concurrently — re-check it"}
    audit.record(uow, user_id, "approve_match", {"finding_id": finding_id})
    return {"ok": True, "finding_id": finding_id, "status": "approved"}


def discard_match(
    uow: UnitOfWork, user_id: int, finding_id: int, reason: str = ""
) -> dict[str, Any]:
    match = hunt.get_match(uow, user_id, finding_id)
    if match is None:
        return {"error": f"match {finding_id} not found"}
    uow.execute(
        "UPDATE explore_findings SET status = 'discarded' WHERE id = ? AND user_id = ?",
        (finding_id, user_id),
    )
    audit.record(uow, user_id, "discard_match", {"finding_id": finding_id, "reason": reason})
    return {"ok": True, "finding_id": finding_id, "status": "discarded"}


def restore_match(uow: UnitOfWork, user_id: int, finding_id: int) -> dict[str, Any]:
    """Re-open a discarded match (discarded → new). The dashboard's undo."""
    match = hunt.get_match(uow, user_id, finding_id)
    if match is None:
        return {"error": f"match {finding_id} not found"}
    if match["status"] != "discarded":
        return {
            "error": f"match {finding_id} is '{match['status']}' — only discarded matches restore"
        }
    # State predicate in the UPDATE itself (concurrent-safe, like approve).
    cur = uow.execute(
        "UPDATE explore_findings SET status = 'new'"
        " WHERE id = ? AND user_id = ? AND status = 'discarded'",
        (finding_id, user_id),
    )
    if cur.rowcount == 0:
        return {"error": f"match {finding_id} changed state concurrently — re-check it"}
    audit.record(uow, user_id, "restore_match", {"finding_id": finding_id})
    return {"ok": True, "finding_id": finding_id, "status": "new"}
