"""Deterministic ATS coverage check — zero LLM.

Classifies each posting keyword against the draft and the candidate's provable
facts: covered (in the draft), missing_but_have (absent from the draft but
present in the facts — the drafter COULD truthfully add it), genuine_gap (in
neither — must be acknowledged, never stuffed). Matching is case-insensitive
with a simple plural strip; no fuzzy/semantic matching by design (determinism
over cleverness).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any


def _stem(word: str) -> str:
    w = word.lower()
    return w[:-1] if w.endswith("s") and len(w) > 3 else w


def _stems(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9+#]+", (text or "").lower())}


def coverage_check(keywords: Sequence[str], asset_text: str, facts_text: str) -> dict[str, Any]:
    """Classify `keywords` against the draft and the facts inventory text."""
    asset_stems = _stems(asset_text)
    facts_stems = _stems(facts_text)
    covered: list[str] = []
    missing_but_have: list[str] = []
    genuine_gaps: list[str] = []
    for kw in keywords:
        stem = _stem(kw)
        if stem in asset_stems:
            covered.append(kw.lower())
        elif stem in facts_stems:
            missing_but_have.append(kw.lower())
        else:
            genuine_gaps.append(kw.lower())
    pct = round(100 * len(covered) / len(keywords)) if keywords else 100
    return {
        "covered": covered,
        "missing_but_have": missing_but_have,
        "genuine_gaps": genuine_gaps,
        "coverage_pct": pct,
    }
