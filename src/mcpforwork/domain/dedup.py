"""Dedup hashing — the stable key derived from a canonical URL.

Pure domain: ``dedup_hash`` is sha256 of the canonical URL, so a posting
hashes identically regardless of tracking params, scheme, ``www.``, or
trailing slash. Persistence and the seen/record use cases live in
``services/dedup.py``.
"""

from __future__ import annotations

import hashlib

from mcpforwork.domain.urls import canonical_url


def dedup_hash(url: str) -> str:
    """sha256 of the canonical URL — the cross-pipeline dedup key."""
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()
