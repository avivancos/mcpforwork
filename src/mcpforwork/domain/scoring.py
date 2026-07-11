"""Finding scoring — driven by the candidate's profile and sector packs.

Deliberately NOT the donor's hardcoded tech persona (PYTHON_API_TERMS, …). The
signal is: does this posting match what THIS candidate is looking for? Terms
come from the profile's target titles and sectors (plus optional sector-pack
terms), so a nurse's profile scores nursing roles highly and a welder's scores
welding roles — sector- and country-agnostic by data (§5).

Pure domain: no I/O, deterministic, no other layer.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

# A salary/compensation mention in the posting text.
_COMP_RE = re.compile(
    r"(€|\beur\b|\$|£|per year|per hour|/yr|/hr|\bsalary\b|\b\d{2,3}\s?k\b)", re.I
)

# Generic words that carry no matching signal.
_STOPWORDS = frozenset(
    {"and", "or", "the", "of", "a", "an", "in", "to", "for", "with", "at", "on", "jobs", "job"}
)

# Per-dimension caps and weights. Title relevance dominates; the rest refine.
_TITLE_CAP, _TITLE_WEIGHT = 4, 12  # up to 48
_SECTOR_CAP, _SECTOR_WEIGHT = 3, 8  # up to 24
_REMOTE_POINTS = 10
_SENIORITY_POINTS = 10
_SALARY_POINTS = 8

_STRONG, _REVIEW = 70, 40


def _terms(phrases: Sequence[str]) -> set[str]:
    """Distinct significant word tokens across the given phrases."""
    terms: set[str] = set()
    for phrase in phrases:
        for word in re.findall(r"[a-z0-9+#]+", str(phrase).lower()):
            if len(word) >= 3 and word not in _STOPWORDS:
                terms.add(word)
    return terms


def _remote_match(finding: Mapping[str, Any], profile: Mapping[str, Any]) -> bool:
    if "remote" not in (profile.get("work_modes") or []):
        return False
    scope = (finding.get("remote_scope") or "").lower()
    location = (finding.get("location") or "").lower()
    return "remote" in scope or "remote" in location or scope in {"worldwide", "anywhere"}


def score_finding(
    finding: Mapping[str, Any], profile: Mapping[str, Any], sector_terms: Sequence[str] = ()
) -> tuple[int, dict[str, int]]:
    """Score a finding 0-100 against a profile. Returns (score, breakdown).

    An empty profile (no titles/sectors) scores only on remote/salary signals —
    it never invents relevance."""
    blob = f"{finding.get('title', '')} {finding.get('description', '')}".lower()

    title_terms = _terms(profile.get("target_titles") or [])
    sector_bag = _terms([*(profile.get("sectors") or []), *sector_terms])

    title_hits = sum(1 for t in title_terms if t in blob)
    sector_hits = sum(1 for t in sector_bag if t in blob)
    seniority = (profile.get("seniority") or "").lower()

    breakdown = {
        "title": min(title_hits, _TITLE_CAP) * _TITLE_WEIGHT,
        "sector": min(sector_hits, _SECTOR_CAP) * _SECTOR_WEIGHT,
        "remote": _REMOTE_POINTS if _remote_match(finding, profile) else 0,
        "seniority": _SENIORITY_POINTS if seniority and seniority in blob else 0,
        "salary": _SALARY_POINTS if (finding.get("salary_text") or _COMP_RE.search(blob)) else 0,
    }
    return min(100, sum(breakdown.values())), breakdown


def determine_action(score: int) -> str:
    """Coarse triage from a score: 'strong' | 'review' | 'new'."""
    if score >= _STRONG:
        return "strong"
    if score >= _REVIEW:
        return "review"
    return "new"
