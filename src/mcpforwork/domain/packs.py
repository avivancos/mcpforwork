"""Source-pack schema + validation.

A pack is versioned DATA: how the copilot searches a set of job sites for a
region or sector. This module is the PURE schema contract — `validate_pack`
returns a list of human-readable errors (empty = valid). Loading the yaml and
selecting sources is `packs/registry.py`.

Clean structured taxonomy (replacing the donor's free-text cat/region): each
source declares ISO-3166 alpha-2 `countries` (or "global"), `sectors` (or
"any"), a `remote` flag, and a `search_playbook`. The playbook's `mode` (default
`url_template`) picks how the client reaches results: `url_template` fills a
`{query}` placeholder into a navigable URL; `search_box` gives a plain search
PAGE and the client types `{query}` into the board's on-page box (for SPA /
Cloudflare boards whose URL-param search does not work — see S2.6).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

PACK_KINDS = frozenset({"global", "country", "sector"})
TIERS = frozenset({"free", "pro"})
# How the client reaches filtered results. `url_template` (default) fills {query}
# into a navigable URL; `search_box` navigates to a plain search PAGE and the
# client types {query} into the board's on-page box (for SPA / Cloudflare boards
# whose URL-param search does not work — verified in S2.6).
SEARCH_MODES = frozenset({"url_template", "search_box"})
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


_APPLY_PLAYBOOK_KEYS = frozenset({"ats_hint", "quirks", "form_url_pattern", "auto_apply_safe"})


def _validate_apply_playbook(apply_pb: Any, where: str) -> list[str]:
    """Shape + https scheme for apply_playbook (S7.2c / ADR 0001 follow-up).

    Clients open form_url_pattern URLs, so scheme validation is load-bearing —
    javascript:/data:/http: must never reach the browser. Unknown keys are
    rejected so pack drift fails loudly rather than being silently ignored.
    """
    if not isinstance(apply_pb, Mapping):
        return [f"{where}.apply_playbook must be a mapping"]
    errors: list[str] = []
    unknown = sorted(set(apply_pb) - _APPLY_PLAYBOOK_KEYS)
    if unknown:
        errors.append(f"{where}.apply_playbook has unknown keys {unknown}")
    if "ats_hint" in apply_pb and not isinstance(apply_pb["ats_hint"], str):
        errors.append(f"{where}.apply_playbook.ats_hint must be a string")
    if "quirks" in apply_pb:
        quirks = apply_pb["quirks"]
        if not isinstance(quirks, list) or not all(isinstance(q, str) for q in quirks):
            errors.append(f"{where}.apply_playbook.quirks must be a list of strings")
    if "form_url_pattern" in apply_pb:
        pattern = apply_pb["form_url_pattern"]
        if not isinstance(pattern, str) or not pattern.startswith("https://"):
            errors.append(f"{where}.apply_playbook.form_url_pattern must be an https URL")
    if "auto_apply_safe" in apply_pb and not isinstance(apply_pb["auto_apply_safe"], bool):
        errors.append(f"{where}.apply_playbook.auto_apply_safe must be a boolean")
    return errors


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
        mode = playbook.get("mode", "url_template")
        if mode not in SEARCH_MODES:
            errors.append(f"{where}.search_playbook.mode must be one of {sorted(SEARCH_MODES)}")
        template = playbook.get("url_template")
        if not isinstance(template, str):
            errors.append(f"{where}.search_playbook.url_template is required")
        else:
            # Packs are untrusted input: the template is handed to the user's
            # browser to open, so its scheme must be http(s) — never javascript:
            # / data: / other schemes.
            if not template.startswith(("http://", "https://")):
                errors.append(f"{where}.search_playbook.url_template must be an http(s) URL")
            # Only url_template mode interpolates the query into the URL. In
            # search_box mode the template is a plain page and {query} is typed
            # on-page, so it is carried in result_hint instead (checked below).
            if mode == "url_template" and "{query}" not in template:
                errors.append(f"{where}.search_playbook.url_template must contain '{{query}}'")
        if mode == "search_box":
            hint = playbook.get("result_hint")
            if not isinstance(hint, str):
                errors.append(f"{where}.search_playbook.result_hint is required in search_box mode")
            elif "{query}" not in hint:
                errors.append(
                    f"{where}.search_playbook.result_hint must contain '{{query}}' (search_box)"
                )

    apply_pb = src.get("apply_playbook")
    if apply_pb is not None:
        errors.extend(_validate_apply_playbook(apply_pb, where))

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
