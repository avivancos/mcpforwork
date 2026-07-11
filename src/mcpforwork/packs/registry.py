"""Load, validate, and select source packs.

Reads the shipped `packs/*.yaml`, validates each against the domain schema
(raising on a malformed pack — a broken pack must never ship silently), and
exposes a `sources_for(...)` selector the hunt pipeline uses to pick sources for
a profile's countries/sectors/work-mode.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import yaml

from mcpforwork.domain.packs import validate_pack

_PACKS_DIR = Path(__file__).parent


class PackError(Exception):
    """A shipped pack failed validation or a slug collided across packs."""


@dataclass(frozen=True)
class PackSource:
    slug: str
    name: str
    base_url: str
    countries: tuple[str, ...]
    sectors: tuple[str, ...]
    remote: bool
    tier: str
    enabled: bool
    url_template: str
    result_hint: str | None
    apply: dict[str, Any]

    def search_url(self, query: str) -> str:
        """The search URL for `query` (target titles), URL-encoded."""
        return self.url_template.replace("{query}", quote_plus(query))


def _to_source(raw: dict[str, Any]) -> PackSource:
    playbook = raw.get("search_playbook", {})
    return PackSource(
        slug=raw["slug"],
        name=raw["name"],
        base_url=raw["base_url"],
        countries=tuple(raw.get("countries", [])),
        sectors=tuple(raw.get("sectors", [])),
        remote=bool(raw.get("remote", False)),
        tier=raw.get("tier", "free"),
        enabled=bool(raw.get("enabled", False)),
        url_template=playbook.get("url_template", ""),
        result_hint=playbook.get("result_hint"),
        apply=raw.get("apply_playbook") or {},
    )


@lru_cache(maxsize=1)
def load_sources() -> dict[str, PackSource]:
    """All sources across all shipped packs, keyed by slug."""
    sources: dict[str, PackSource] = {}
    for path in sorted(_PACKS_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        errors = validate_pack(data)
        if errors:
            raise PackError(f"invalid pack {path.name}: {errors}")
        for raw in data["sources"]:
            src = _to_source(raw)
            if src.slug in sources:
                raise PackError(f"duplicate slug across packs: '{src.slug}'")
            sources[src.slug] = src
    return sources


def _tags_match(tags: tuple[str, ...], wanted: Sequence[str], wildcard: str) -> bool:
    if wildcard in tags:
        return True
    return bool({t.upper() for t in tags} & {w.upper() for w in wanted})


def sources_for(
    countries: Sequence[str] | None = None,
    sectors: Sequence[str] | None = None,
    remote: bool | None = None,
    *,
    enabled_only: bool = True,
) -> list[PackSource]:
    """Select sources whose country/sector tags overlap the request. A "global"
    country tag or "any" sector tag matches anything. `remote=True` keeps only
    remote-friendly boards; `None` does not filter on mode."""
    out: list[PackSource] = []
    for src in load_sources().values():
        if enabled_only and not src.enabled:
            continue
        if remote is not None and remote and not src.remote:
            continue
        if countries and not _tags_match(src.countries, countries, "global"):
            continue
        if sectors and not _tags_match(src.sectors, sectors, "any"):
            continue
        out.append(src)
    return out
