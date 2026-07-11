"""Asset use cases: store and version the drafts the client LLM produced."""

from __future__ import annotations

from typing import Any

from mcpforwork.ports.db import Row, UnitOfWork
from mcpforwork.services import audit
from mcpforwork.services.briefs import ASSET_TYPES


def _owned_finding(uow: UnitOfWork, user_id: int, finding_id: int) -> bool:
    return (
        uow.fetchone(
            "SELECT id FROM explore_findings WHERE id = ? AND user_id = ?", (finding_id, user_id)
        )
        is not None
    )


def submit_asset(
    uow: UnitOfWork, user_id: int, finding_id: int, asset_type: str, content: str
) -> dict[str, Any]:
    """Store a draft; versions auto-increment per (finding, asset_type). The
    caller commits."""
    if asset_type not in ASSET_TYPES:
        return {"error": f"asset_type must be one of {sorted(ASSET_TYPES)}"}
    if not (content or "").strip():
        return {"error": "content is empty"}
    if not _owned_finding(uow, user_id, finding_id):
        return {"error": f"match {finding_id} not found"}
    current = uow.fetchone(
        "SELECT COALESCE(MAX(version), 0) AS v FROM generated_assets"
        " WHERE user_id = ? AND finding_id = ? AND asset_type = ?",
        (user_id, finding_id, asset_type),
    )
    version = current["v"] + 1
    asset_id = uow.insert(
        "INSERT INTO generated_assets (user_id, finding_id, asset_type, content, version)"
        " VALUES (?, ?, ?, ?, ?)",
        (user_id, finding_id, asset_type, content, version),
    )
    audit.record(
        uow,
        user_id,
        "submit_asset",
        {"finding_id": finding_id, "asset_type": asset_type, "version": version},
    )
    return {"ok": True, "asset_id": asset_id, "version": version}


def get_assets(
    uow: UnitOfWork, user_id: int, finding_id: int, asset_type: str | None = None
) -> list[Row]:
    """The finding's drafts, newest version first."""
    sql = "SELECT * FROM generated_assets WHERE user_id = ? AND finding_id = ?"
    params: list[Any] = [user_id, finding_id]
    if asset_type:
        sql += " AND asset_type = ?"
        params.append(asset_type)
    sql += " ORDER BY asset_type, version DESC"
    return uow.fetchall(sql, params)
