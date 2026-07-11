"""Zero-LLM CV parsing — the self-host onboarding default (§1 zero-cost).

Ported from startup-jobs-radar's regex parser. Pure stdlib; low-confidence
fields come back as None so the client asks the human instead of inventing.
There is deliberately NO LLM path here: the client LLM (already paid by the
user) does any richer interpretation and confirms with the human.
"""

from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"[+\d][\d\s\-()]{6,}")
_URL_RE = re.compile(r"https?://\S+")
_LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/\S+", re.IGNORECASE)
_GITHUB_RE = re.compile(r"https?://(?:www\.)?github\.com/\S+", re.IGNORECASE)
_NAME_LABEL_RE = re.compile(r"^\s*name\s*[:\-]\s*(.+)$", re.IGNORECASE)
_SECTION_HEADER_RE = re.compile(
    r"^\s*(EXPERIENCE|EDUCATION|SKILLS|WORK|SUMMARY|PROFILE|PROJECTS|ABOUT)\b", re.IGNORECASE
)


def _strip_trailing_punct(value: str) -> str:
    return value.strip().rstrip(".,;:)]>\"'")


def _header_block(cv_text: str) -> list[str]:
    """Leading lines before the first section header (max 12 non-blank) —
    bounding contact extraction here keeps an EXPERIENCE title from becoming
    the candidate's name."""
    header: list[str] = []
    for line in cv_text.splitlines():
        if _SECTION_HEADER_RE.match(line):
            break
        header.append(line)
        if len([ln for ln in header if ln.strip()]) >= 12:
            break
    return header


def _extract_name(header: list[str]) -> str | None:
    for raw in header:
        match = _NAME_LABEL_RE.match(raw)
        if match and match.group(1).strip():
            return match.group(1).strip()
    for raw in header:
        line = raw.strip()
        if not line:
            continue
        if _EMAIL_RE.search(line) or _URL_RE.search(line) or _SECTION_HEADER_RE.match(line):
            return None  # not a name — leave it to the human
        if len(line.split()) > 5:
            return None  # a sentence, not a name (stricter than the donor)
        return line
    return None


def extract_profile_from_cv(cv_text: str) -> dict:
    """Parse CV text into profile-shaped fields. None = low confidence."""
    header = _header_block(cv_text)

    email_match = _EMAIL_RE.search(cv_text)  # contact info may sit at the bottom
    phone = None
    for raw in header:  # body numbers are dates, not phones
        match = _PHONE_RE.search(raw)
        if match:
            candidate = _strip_trailing_punct(match.group(0))
            # >= 9 digits: rejects date ranges like "2020-2023" (8 digits),
            # which the donor's >= 7 threshold let through.
            if sum(ch.isdigit() for ch in candidate) >= 9:
                phone = candidate
                break

    linkedin = _LINKEDIN_RE.search(cv_text)
    github = _GITHUB_RE.search(cv_text)
    portfolio = None
    for url in _URL_RE.finditer(cv_text):
        candidate = _strip_trailing_punct(url.group(0))
        if _LINKEDIN_RE.match(candidate) or _GITHUB_RE.match(candidate):
            continue
        portfolio = candidate
        break

    return {
        "candidate": {
            "full_name": _extract_name(header),
            "contact_email": email_match.group(0) if email_match else None,
            "phone": phone,
            "linkedin": _strip_trailing_punct(linkedin.group(0)) if linkedin else None,
            "github": _strip_trailing_punct(github.group(0)) if github else None,
            "portfolio": _strip_trailing_punct(portfolio) if portfolio else None,
        },
        "cv_text": cv_text,
    }
