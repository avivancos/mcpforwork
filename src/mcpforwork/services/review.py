"""Review use cases: approve / discard a scouted match (audited).

Error dicts carry a structured `kind` (`not_found` / `invalid_state`) next to
the human message — entrypoints map kinds to status codes, never substrings.
The MCP tools read only `error`; the kind is additive.
"""

from __future__ import annotations

from typing import Any

from mcpforwork.ports.db import UnitOfWork
from mcpforwork.services import audit, hunt

# States a match can be approved from. Terminal states (discarded,
# applied_external) require an explicit human re-open, not a silent flip.
_APPROVABLE = frozenset({"new", "review"})


def _not_found(finding_id: int) -> dict[str, Any]:
    # Unknown and foreign matches are indistinguishable (both not_found).
    return {"error": f"match {finding_id} not found", "kind": "not_found"}


def approve_match(uow: UnitOfWork, user_id: int, finding_id: int) -> dict[str, Any]:
    match = hunt.get_match(uow, user_id, finding_id)
    if match is None:
        return _not_found(finding_id)
    if match["status"] not in _APPROVABLE:
        return {
            "error": f"match {finding_id} is '{match['status']}' — cannot approve",
            "kind": "invalid_state",
        }
    # State predicate in the UPDATE itself: a concurrent discard between the
    # read above and this write must not be silently overwritten.
    cur = uow.execute(
        "UPDATE explore_findings SET status = 'approved'"
        " WHERE id = ? AND user_id = ? AND status IN ('new', 'review')",
        (finding_id, user_id),
    )
    if cur.rowcount == 0:
        return {
            "error": f"match {finding_id} changed state concurrently — re-check it",
            "kind": "invalid_state",
        }
    audit.record(uow, user_id, "approve_match", {"finding_id": finding_id})
    return {"ok": True, "finding_id": finding_id, "status": "approved"}


def discard_match(
    uow: UnitOfWork, user_id: int, finding_id: int, reason: str = ""
) -> dict[str, Any]:
    match = hunt.get_match(uow, user_id, finding_id)
    if match is None:
        return _not_found(finding_id)
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
        return _not_found(finding_id)
    if match["status"] != "discarded":
        return {
            "error": (
                f"match {finding_id} is '{match['status']}' — only discarded matches restore"
            ),
            "kind": "invalid_state",
        }
    # State predicate in the UPDATE itself (concurrent-safe, like approve).
    cur = uow.execute(
        "UPDATE explore_findings SET status = 'new'"
        " WHERE id = ? AND user_id = ? AND status = 'discarded'",
        (finding_id, user_id),
    )
    if cur.rowcount == 0:
        return {
            "error": f"match {finding_id} changed state concurrently — re-check it",
            "kind": "invalid_state",
        }
    audit.record(uow, user_id, "restore_match", {"finding_id": finding_id})
    return {"ok": True, "finding_id": finding_id, "status": "new"}
