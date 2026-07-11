"""Hunt use cases — the search side of the copilot.

From the active profile + packs, produce per-source search playbooks the client
LLM browses in the user's own browser; ingest the findings it extracts (deduped
across external_applications AND explore_findings, scored by the profile,
persisted); and surface the matches. The server never browses — it choreographs.

Signatures are `(uow, user_id, ...)`; the caller owns the transaction.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from mcpforwork.domain.dedup import dedup_hash
from mcpforwork.domain.scoring import determine_action, score_finding
from mcpforwork.packs import registry
from mcpforwork.ports.db import Row, UnitOfWork
from mcpforwork.services import audit, profiles

# Descriptive fields a re-sight may enrich (merged over the stored finding).
_DESCRIPTIVE_FIELDS = (
    "title",
    "company_name",
    "location",
    "remote_scope",
    "salary_text",
    "description",
)


def _utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _wants_remote(profile: Mapping[str, Any]) -> bool | None:
    modes = profile.get("work_modes") or []
    if not modes:
        return None
    if modes == ["remote"]:
        return True
    if "remote" not in modes:
        return False
    return None


def hunt_plan(uow: UnitOfWork, user_id: int) -> dict[str, Any]:
    """Per-source search playbooks for the active profile — the URLs the client
    opens in its browser. Selects sources by the profile's countries/sectors/
    work-mode and fills each `url_template` with the target titles."""
    profile = profiles.get_profile(uow, user_id)
    if profile is None:
        return {"error": "no active profile — run /setup (update_profile) first"}

    titles = profile.get("target_titles") or []
    query = " ".join(titles[:2]).strip()
    sources = registry.sources_for(
        countries=profile.get("work_auth_countries") or None,
        sectors=profile.get("sectors") or None,
        remote=_wants_remote(profile),
    )
    plan = [
        {
            "slug": s.slug,
            "name": s.name,
            "search_url": s.search_url(query) if query else s.base_url,
            "result_hint": s.result_hint,
            "apply_hint": s.apply.get("ats_hint"),
        }
        for s in sources
    ]
    return {"query": query, "count": len(plan), "sources": plan}


def source_playbook(slug: str, query: str = "") -> dict[str, Any]:
    """The full playbook (search + apply) for one source."""
    source = registry.load_sources().get(slug)
    if source is None:
        return {"error": f"unknown source: {slug}"}
    return {
        "slug": source.slug,
        "name": source.name,
        "base_url": source.base_url,
        "countries": list(source.countries),
        "sectors": list(source.sectors),
        "search_url": source.search_url(query) if query else source.url_template,
        "result_hint": source.result_hint,
        "apply_playbook": source.apply,
    }


def list_sources(
    countries: Sequence[str] | None = None, sectors: Sequence[str] | None = None
) -> list[dict[str, Any]]:
    sources = registry.sources_for(countries=countries, sectors=sectors)
    return [
        {
            "slug": s.slug,
            "name": s.name,
            "countries": list(s.countries),
            "sectors": list(s.sectors),
            "remote": s.remote,
            "tier": s.tier,
        }
        for s in sources
    ]


def submit_findings(
    uow: UnitOfWork, user_id: int, source_slug: str, findings: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Ingest postings the client extracted from `source_slug`: skip blanks and
    URLs already applied to (external_applications); score each against the
    active profile; upsert into explore_findings (re-scoring on re-sight)."""
    if source_slug not in registry.load_sources():
        return {"error": f"unknown source: {source_slug}"}

    profile = profiles.get_profile(uow, user_id) or {}
    stats = {"submitted": len(findings), "new": 0, "seen_again": 0, "skipped": 0}
    for raw in findings:
        if not isinstance(raw, Mapping):
            stats["skipped"] += 1
            continue
        url = (raw.get("url") or "").strip()
        title = (raw.get("title") or "").strip()
        if not title or not url.startswith(("http://", "https://")):
            stats["skipped"] += 1
            continue
        digest = dedup_hash(url)
        if uow.fetchone(
            "SELECT id FROM external_applications WHERE dedup_hash = ? AND user_id = ?",
            (digest, user_id),
        ):
            stats["seen_again"] += 1  # already hand-applied — never re-enter the pipeline
            continue

        existing = uow.fetchone(
            "SELECT * FROM explore_findings WHERE dedup_hash = ? AND user_id = ?",
            (digest, user_id),
        )
        if existing is not None:
            # Re-sight: merge the new extraction over the stored one (a sparser
            # re-sight never erases richer data), re-score, and bump last_seen.
            merged = dict(existing)
            for field in _DESCRIPTIVE_FIELDS:
                if raw.get(field):
                    merged[field] = raw[field]
            score, breakdown = score_finding(merged, profile)
            uow.execute(
                "UPDATE explore_findings SET last_seen = ?, title = ?, company_name = ?,"
                " location = ?, remote_scope = ?, salary_text = ?, description = ?,"
                " score = ?, score_breakdown = ?, action = ? WHERE id = ? AND user_id = ?",
                (
                    _utcnow_iso(),
                    merged["title"],
                    merged.get("company_name"),
                    merged.get("location"),
                    merged.get("remote_scope"),
                    merged.get("salary_text"),
                    merged.get("description"),
                    score,
                    json.dumps(breakdown),
                    determine_action(score),
                    existing["id"],
                    user_id,
                ),
            )
            stats["seen_again"] += 1
        else:
            score, breakdown = score_finding(raw, profile)
            action = determine_action(score)
            uow.insert(
                "INSERT INTO explore_findings (user_id, source_slug, dedup_hash, url, title,"
                " company_name, location, remote_scope, salary_text, description, score,"
                " score_breakdown, status, action)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user_id,
                    source_slug,
                    digest,
                    url,
                    title,
                    raw.get("company_name"),
                    raw.get("location"),
                    raw.get("remote_scope"),
                    raw.get("salary_text"),
                    raw.get("description"),
                    score,
                    json.dumps(breakdown),
                    "new",
                    action,
                ),
            )
            stats["new"] += 1

    audit.record(
        uow,
        user_id,
        "submit_findings",
        {"source": source_slug, "new": stats["new"], "seen_again": stats["seen_again"]},
    )
    return {"source_slug": source_slug, **stats}


def _deserialize(row: Row) -> Row:
    out = dict(row)
    if out.get("score_breakdown") is not None:
        out["score_breakdown"] = json.loads(out["score_breakdown"])
    return out


def list_matches(
    uow: UnitOfWork,
    user_id: int,
    min_score: int = 0,
    status: str | None = None,
    limit: int = 50,
) -> list[Row]:
    """Findings at or above `min_score`, best first."""
    sql = "SELECT * FROM explore_findings WHERE user_id = ? AND score >= ?"
    params: list[Any] = [user_id, min_score]
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY score DESC, id DESC LIMIT ?"
    params.append(limit)
    return [_deserialize(r) for r in uow.fetchall(sql, params)]


def get_match(uow: UnitOfWork, user_id: int, finding_id: int) -> Row | None:
    row = uow.fetchone(
        "SELECT * FROM explore_findings WHERE user_id = ? AND id = ?", (user_id, finding_id)
    )
    return _deserialize(row) if row is not None else None
