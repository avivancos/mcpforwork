"""Autopilot consent artifacts (S7.2a, ADR 0005).

THE write side of consent: approval artifacts are written exclusively here,
behind the human-session HTTP API. The MCP entrypoint never imports this
module — no sequence of agent tool calls (possibly prompt-injected by posting
content) can mint consent. Reads stay in services/apply.py, which evaluates
the recorded artifact inside request_submit.
"""

from __future__ import annotations

from typing import Any

from mcpforwork.ports.db import UnitOfWork
from mcpforwork.services import audit
from mcpforwork.services.clock import utcnow_iso

# Approval is meaningful exactly while the human is being asked: the two
# states the dashboard derives as "awaiting you".
_APPROVABLE_STATES = ("awaiting_human", "submit_requested")


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
