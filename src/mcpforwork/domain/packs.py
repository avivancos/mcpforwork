"""Source-pack schema + validation.

A pack is versioned DATA: how the copilot searches a set of job sites for a
region or sector. This module is the PURE schema contract — `validate_pack`
returns a list of human-readable errors (empty = valid). Loading the yaml and
selecting sources is `packs/registry.py`.

Clean structured taxonomy (replacing the donor's free-text cat/region): each
source declares ISO-3166 alpha-2 `countries` (or "global"), `sectors` (or
"any"), a `remote` flag, and a `search_playbook.url_template` carrying a
`{query}` placeholder the client fills with the candidate's target titles.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

PACK_KINDS = frozenset({"global", "country", "sector"})
TIERS = frozenset({"free", "pro"})
_ISO_ALPHA2 = re.compile(r"^[A-Z]{2}$")


def _valid_country(code: object) -> bool:
    return code == "global" or (isinstance(code, str) and bool(_ISO_ALPHA2.match(code)))


def _check_string_list(src: Mapping[str, Any], field: str, where: str) -> list[str]:
    value = src.get(field)
    if not isinstance(value, list) or not value:
        return [f"{where}.{field} must be a non-empty list"]
    if not all(isinstance(item, str) for item in value):
        return [f"{where}.{field} must be a list of strings"]
    return []


def _validate_source(src: Any, where: str, seen_slugs: set[str]) -> list[str]:
    if not isinstance(src, Mapping):
        return [f"{where} must be a mapping"]
    errors: list[str] = []

    slug = src.get("slug")
    if not slug or not isinstance(slug, str):
        errors.append(f"{where}.slug is required")
    else:
        where = f"source '{slug}'"
        if slug in seen_slugs:
            errors.append(f"duplicate slug '{slug}'")
        seen_slugs.add(slug)

    if not src.get("name"):
        errors.append(f"{where}.name is required")

    base = src.get("base_url")
    if not isinstance(base, str) or not base.startswith(("http://", "https://")):
        errors.append(f"{where}.base_url must be an http(s) URL")

    country_errors = _check_string_list(src, "countries", where)
    errors.extend(country_errors)
    if not country_errors:
        bad = [c for c in src["countries"] if not _valid_country(c)]
        if bad:
            errors.append(f"{where}.countries has invalid codes {bad} (ISO alpha-2 or 'global')")

    errors.extend(_check_string_list(src, "sectors", where))

    if src.get("tier", "free") not in TIERS:
        errors.append(f"{where}.tier must be one of {sorted(TIERS)}")
    for flag in ("remote", "enabled"):
        if flag in src and not isinstance(src[flag], bool):
            errors.append(f"{where}.{flag} must be a boolean")

    playbook = src.get("search_playbook")
    if not isinstance(playbook, Mapping):
        errors.append(f"{where}.search_playbook is required")
    else:
        template = playbook.get("url_template")
        if not isinstance(template, str) or "{query}" not in template:
            errors.append(f"{where}.search_playbook.url_template must contain '{{query}}'")

    apply_pb = src.get("apply_playbook")
    if apply_pb is not None:
        if not isinstance(apply_pb, Mapping):
            errors.append(f"{where}.apply_playbook must be a mapping")
        elif "auto_apply_safe" in apply_pb and not isinstance(apply_pb["auto_apply_safe"], bool):
            errors.append(f"{where}.apply_playbook.auto_apply_safe must be a boolean")

    return errors


def validate_pack(data: Any) -> list[str]:
    """Return a list of validation errors for a parsed pack (empty = valid)."""
    if not isinstance(data, Mapping):
        return ["pack file must be a mapping with 'pack' and 'sources'"]

    errors: list[str] = []
    meta = data.get("pack")
    if not isinstance(meta, Mapping):
        errors.append("missing 'pack' metadata block")
    else:
        if not meta.get("id"):
            errors.append("pack.id is required")
        if not isinstance(meta.get("version"), int):
            errors.append("pack.version must be an integer")
        if meta.get("kind") not in PACK_KINDS:
            errors.append(f"pack.kind must be one of {sorted(PACK_KINDS)}")

    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("'sources' must be a non-empty list")
        return errors

    seen_slugs: set[str] = set()
    for i, src in enumerate(sources):
        errors.extend(_validate_source(src, f"sources[{i}]", seen_slugs))
    return errors
