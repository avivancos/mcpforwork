"""ats_coverage_check use case: posting keywords vs a stored draft vs the facts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mcpforwork.domain.brief import build_facts_inventory, extract_keywords
from mcpforwork.domain.coverage import coverage_check
from mcpforwork.ports.db import UnitOfWork
from mcpforwork.services import hunt, profiles


def _flatten_values(value: Any) -> list[str]:
    """Leaf STRING values only — the user's own words. No dict keys (schema
    column names are not facts), no numbers/timestamps (a bare figure is not a
    claimable skill), no JSON punctuation."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [s for v in value.values() for s in _flatten_values(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _flatten_values(v)]
    return []


def _facts_text(uow: UnitOfWork, user_id: int) -> str:
    """The SAME source of truth the brief binds the drafter to: the facts
    inventory's leaf values. Anything outside it is not 'truthfully addable'."""
    facts = profiles.export_for_brief(uow, user_id)
    if facts is None:
        return ""
    achievements = profiles.list_achievements(uow, user_id, facts["id"])
    return " ".join(_flatten_values(build_facts_inventory(facts, achievements)))


def ats_coverage_check(
    uow: UnitOfWork, user_id: int, finding_id: int, asset_id: int
) -> dict[str, Any]:
    """Deterministic coverage of the posting's keywords by the stored draft."""
    match = hunt.get_match(uow, user_id, finding_id)
    if match is None:
        return {"error": f"match {finding_id} not found"}
    asset = uow.fetchone(
        "SELECT content FROM generated_assets WHERE id = ? AND user_id = ? AND finding_id = ?",
        (asset_id, user_id, finding_id),
    )
    if asset is None:
        return {"error": f"asset {asset_id} not found for match {finding_id}"}
    keywords = extract_keywords(match["title"], match.get("description") or "")
    result = coverage_check(keywords, asset["content"], _facts_text(uow, user_id))
    result["finding_id"] = finding_id
    result["asset_id"] = asset_id
    result["keywords"] = keywords
    return result
