"""Crowd-learning capture: what worked / moved / broke on a source's playbook.

Opt-in reports feed the pack-update pipeline (S8 ingests them into new pack
versions via maintainer review). The caller commits.
"""

from __future__ import annotations

import json
from typing import Any

from mcpforwork.packs import registry
from mcpforwork.ports.db import UnitOfWork
from mcpforwork.services import audit

KINDS = frozenset({"success", "drift", "break"})


def report_playbook_result(
    uow: UnitOfWork, user_id: int, source_slug: str, kind: str, diff: dict[str, Any]
) -> dict[str, Any]:
    if source_slug not in registry.load_sources():
        return {"error": f"unknown source: {source_slug}"}
    if kind not in KINDS:
        return {"error": f"kind must be one of {sorted(KINDS)}"}
    report_id = uow.insert(
        "INSERT INTO playbook_reports (user_id, source_slug, kind, diff) VALUES (?, ?, ?, ?)",
        (user_id, source_slug, kind, json.dumps(diff or {})),
    )
    audit.record(uow, user_id, "report_playbook_result", {"source": source_slug, "kind": kind})
    return {"ok": True, "report_id": report_id}
