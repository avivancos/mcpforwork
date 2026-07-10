"""Dedup + application-tracking use cases.

One invariant: never touch the same opportunity twice without knowing.

- ``check_seen``: given a batch of URLs, report what the copilot already knows —
  today that is the ``external_applications`` table (hand/external applies:
  LinkedIn Easy Apply, apply-by-email, company web forms). The scouted
  ``findings``/``matches`` sources are added here when the hunt pipeline lands
  (S2), so callers should treat the returned shape as source-agnostic.
- ``record_application``: write a hand/external application, idempotent by
  ``(user_id, dedup_hash)``, so the next ``check_seen`` skips it.
- ``recompute_hashes``: re-canonicalise stored hashes and merge tracking-param
  duplicates — the backfill run after any ``canonical_url`` change.

Signatures are ``(uow, user_id, ...)``; the caller owns the transaction.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from mcpforwork.domain.dedup import dedup_hash
from mcpforwork.ports.db import UnitOfWork


def _utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _audit(uow: UnitOfWork, user_id: int, action: str, detail: dict[str, Any]) -> None:
    uow.insert(
        "INSERT INTO audit_log (user_id, action, detail) VALUES (?, ?, ?)",
        (user_id, action, json.dumps(detail)),
    )


def check_seen(uow: UnitOfWork, user_id: int, urls: Sequence[str]) -> dict[str, Any]:
    """Report what the copilot already knows about each URL.

    Per URL: ``{url, seen, applied, discarded, status, source,
    external_application_id, recommendation}`` where ``recommendation`` is
    ``"skip"`` when already recorded and ``"new"`` otherwise. External
    applications are terminal (applied), so a hit is both ``seen`` and
    ``applied``.
    """
    items: list[dict[str, Any]] = []
    new_urls: list[str] = []
    seen_urls: list[str] = []
    for raw_url in urls:
        url = (raw_url or "").strip()
        if not url:
            continue
        digest = dedup_hash(url)
        ext = uow.fetchone(
            "SELECT id FROM external_applications WHERE dedup_hash = ? AND user_id = ?",
            (digest, user_id),
        )
        seen = ext is not None
        items.append(
            {
                "url": url,
                "seen": seen,
                "applied": seen,
                "discarded": False,
                "status": "applied_external" if seen else None,
                "source": "external_application" if seen else None,
                "external_application_id": ext["id"] if ext else None,
                "recommendation": "skip" if seen else "new",
            }
        )
        (seen_urls if seen else new_urls).append(url)

    return {
        "checked": len(items),
        "new_count": len(new_urls),
        "seen_count": len(seen_urls),
        "new_urls": new_urls,
        "seen_urls": seen_urls,
        "items": items,
    }


def record_application(
    uow: UnitOfWork,
    user_id: int,
    *,
    url: str = "",
    channel: str = "",
    method: str = "",
    title: str = "",
    company_name: str = "",
    finding_id: int | None = None,
    notes: str = "",
    applied_at: str = "",
) -> dict[str, Any]:
    """Record a hand/external application so the copilot stops re-surfacing it.

    Idempotent by ``(user_id, dedup_hash)``: a second call for the same URL
    updates the existing row (``deduped=True``) rather than inserting a
    duplicate. Does NOT commit — the caller owns the transaction.
    """
    url = (url or "").strip()
    if not url:
        return {"error": "record_application needs a url"}
    channel = (channel or "external").strip()
    digest = dedup_hash(url)
    when = applied_at or _utcnow_iso()

    existing = uow.fetchone(
        "SELECT id FROM external_applications WHERE dedup_hash = ? AND user_id = ?",
        (digest, user_id),
    )
    deduped = existing is not None
    if existing is not None:
        uow.execute(
            "UPDATE external_applications SET channel = ?, method = ?, notes = ?,"
            " applied_at = ?, finding_id = COALESCE(?, finding_id),"
            " company_name = COALESCE(?, company_name), title = COALESCE(?, title)"
            " WHERE id = ? AND user_id = ?",
            (
                channel,
                method or None,
                notes or None,
                when,
                finding_id,
                company_name or None,
                title or None,
                existing["id"],
                user_id,
            ),
        )
        ext_id = existing["id"]
    else:
        ext_id = uow.insert(
            "INSERT INTO external_applications"
            " (user_id, finding_id, url, company_name, title, channel, method,"
            " dedup_hash, applied_at, notes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                finding_id,
                url,
                company_name or None,
                title or None,
                channel,
                method or None,
                digest,
                when,
                notes or None,
            ),
        )

    _audit(uow, user_id, "record_application", {"url": url, "channel": channel, "deduped": deduped})
    return {"ok": True, "external_application_id": ext_id, "deduped": deduped, "url": url}


def recompute_hashes(uow: UnitOfWork, user_id: int) -> dict[str, Any]:
    """Re-canonicalise every external-application hash and merge duplicates.

    For each row: if the recomputed hash already matches, skip. If another row
    now holds the recomputed hash, merge — the lower id survives (both rows are
    terminal applied_external, so rank is equal) — deleting the loser and
    taking the canonical hash. Idempotent; the caller commits.
    """
    updated = 0
    merged = 0
    skipped = 0
    rows = uow.fetchall(
        "SELECT id, url, dedup_hash FROM external_applications WHERE user_id = ? ORDER BY id",
        (user_id,),
    )
    for row in rows:
        url = row["url"] or ""
        if not url:
            skipped += 1
            continue
        new_hash = dedup_hash(url)
        if new_hash == row["dedup_hash"]:
            skipped += 1
            continue
        collision = uow.fetchone(
            "SELECT id FROM external_applications WHERE dedup_hash = ? AND user_id = ? AND id != ?",
            (new_hash, user_id, row["id"]),
        )
        if collision is None:
            uow.execute(
                "UPDATE external_applications SET dedup_hash = ? WHERE id = ? AND user_id = ?",
                (new_hash, row["id"], user_id),
            )
            updated += 1
            continue
        # Merge: lower id survives. Delete the loser first so the winner can
        # take the canonical hash without tripping UNIQUE(user_id, dedup_hash).
        if collision["id"] < row["id"]:
            winner_id, loser_id = collision["id"], row["id"]
        else:
            winner_id, loser_id = row["id"], collision["id"]
        uow.execute(
            "DELETE FROM external_applications WHERE id = ? AND user_id = ?", (loser_id, user_id)
        )
        uow.execute(
            "UPDATE external_applications SET dedup_hash = ? WHERE id = ? AND user_id = ?",
            (new_hash, winner_id, user_id),
        )
        merged += 1

    return {"updated": updated, "merged": merged, "skipped": skipped}
