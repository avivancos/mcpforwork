"""Audit-log writes — the shared trail every state-changing service appends to.

`audit_log` is cross-cutting (not RLS-forced): a durable record of who did what.
The caller owns the transaction.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from mcpforwork.ports.db import UnitOfWork


def _iso(value: Any) -> str:
    # SQLite stores ISO text; Postgres returns datetime. Normalise to ISO-8601
    # so the {at, event} shape is identical on both dialects.
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def record(
    uow: UnitOfWork, user_id: int, action: str, detail: dict[str, Any] | None = None
) -> None:
    uow.insert(
        "INSERT INTO audit_log (user_id, action, detail) VALUES (?, ?, ?)",
        (user_id, action, json.dumps(detail or {})),
    )


def recent(uow: UnitOfWork, user_id: int, limit: int = 100) -> list[dict[str, Any]]:
    """The user's own audit rows, newest first, as {at, event} pairs.

    `audit_log` is NOT RLS-forced — this explicit user_id filter is the tenant
    wall (same rule as the pipeline reads)."""
    rows = uow.fetchall(
        "SELECT action, detail, created_at FROM audit_log"
        " WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    events = []
    for row in rows:
        try:
            detail = json.loads(row["detail"] or "{}")
        except (TypeError, ValueError):
            detail = {}
        event = row["action"]
        if detail.get("summary"):
            event = f"{event} — {detail['summary']}"
        events.append({"at": _iso(row["created_at"]), "event": event})
    return events
