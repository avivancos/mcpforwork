"""Zero-LLM CV parsing — the self-host onboarding default (§1 zero-cost).

Ported from startup-jobs-radar's regex parser. Pure stdlib; low-confidence
fields come back as None so the client asks the human instead of inventing.
There is deliberately NO LLM path here: the client LLM (already paid by the
user) does any richer interpretation and confirms with the human.
"""

from __future__ import annotations

import re

# Bounded quantifiers: an unbounded `[\w.+-]+@` backtracks quadratically over a
# long non-@ run of word chars (a ReDoS on the arbitrary text parse_cv accepts).
# RFC caps: local part 64, domain label 255, TLD is short. Linear at any size.
_EMAIL_RE = re.compile(r"[\w.+-]{1,64}@[\w-]{1,255}\.[a-zA-Z]{2,24}")
_PHONE_RE = re.compile(r"[+\d][\d\s\-()]{6,24}")
_URL_RE = re.compile(r"https?://\S+")

# A CV over this size is pathological, not a résumé — the parse_cv tool rejects it.
MAX_CV_CHARS = 200_000
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
        # Anything that is clearly not a name -> None (ask the human, never invent).
        if _EMAIL_RE.search(line) or _URL_RE.search(line) or _SECTION_HEADER_RE.match(line):
            return None
        if line.endswith(":"):
            return None  # a field label ("Name:", "Contact:"), not a value
        if sum(ch.isdigit() for ch in line) >= 7:
            return None  # a phone / id line, not a name
        if len(line.split()) > 5:
            return None  # a sentence, not a name
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
            "portfolio": portfolio,  # already stripped in the loop above
        },
        "cv_text": cv_text,
    }
