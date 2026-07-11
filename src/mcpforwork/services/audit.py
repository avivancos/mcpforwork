"""Audit-log writes — the shared trail every state-changing service appends to.

`audit_log` is cross-cutting (not RLS-forced): a durable record of who did what.
The caller owns the transaction.
"""

from __future__ import annotations

import json
from typing import Any

from mcpforwork.ports.db import UnitOfWork


def record(
    uow: UnitOfWork, user_id: int, action: str, detail: dict[str, Any] | None = None
) -> None:
    uow.insert(
        "INSERT INTO audit_log (user_id, action, detail) VALUES (?, ?, ?)",
        (user_id, action, json.dumps(detail or {})),
    )
