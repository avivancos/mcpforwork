"""Generation-brief use case: assemble the structure the client LLM drafts from."""

from __future__ import annotations

from typing import Any

from mcpforwork.domain.brief import (
    HONESTY_RULES,
    PRINT_TEMPLATE,
    build_facts_inventory,
    extract_keywords,
)
from mcpforwork.ports.db import UnitOfWork
from mcpforwork.services import hunt, profiles

ASSET_TYPES = frozenset({"cv", "cover_letter"})


def get_generation_brief(
    uow: UnitOfWork, user_id: int, finding_id: int, asset_type: str
) -> dict[str, Any]:
    """The structured brief for drafting `asset_type` against one match.

    Deterministic; salary is redacted by profiles.export_for_brief (the privacy
    gate) before the facts inventory is built.
    """
    if asset_type not in ASSET_TYPES:
        return {"error": f"asset_type must be one of {sorted(ASSET_TYPES)}"}
    match = hunt.get_match(uow, user_id, finding_id)
    if match is None:
        return {"error": f"match {finding_id} not found"}
    facts = profiles.export_for_brief(uow, user_id)  # salary redacted
    if facts is None:
        return {"error": "no active profile — run /setup first"}
    achievements = profiles.list_achievements(uow, user_id, facts["id"])
    style = profiles.get_style_profile(uow, user_id, facts["id"]) or {}

    return {
        "asset_type": asset_type,
        "job": {
            "finding_id": match["id"],
            "title": match["title"],
            "company": match.get("company_name"),
            "url": match["url"],
            "location": match.get("location"),
            "description": match.get("description"),
            "keywords": extract_keywords(match["title"], match.get("description") or ""),
        },
        "facts_inventory": build_facts_inventory(facts, achievements),
        "style": {
            "writing_sample": style.get("writing_sample"),
            "directives": style.get("directives"),
        },
        "honesty_rules": list(HONESTY_RULES),
        "format": {"medium": "markdown", "print_template": PRINT_TEMPLATE},
        "language_hint": "match the posting's language",
    }
