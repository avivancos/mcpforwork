"""Zero-LLM CV parsing — the self-host onboarding default (§1 zero-cost).

Ported from startup-jobs-radar's regex parser. Pure stdlib; low-confidence
fields come back as None so the client asks the human instead of inventing.
There is deliberately NO LLM path here: the client LLM (already paid by the
user) does any richer interpretation and confirms with the human.

S5.3 adds evidence-only `setup_hints` (work modes, employment types, top
allowlisted skills, signals) so /setup can focus without inventing titles or
seniority on the server.
"""

from __future__ import annotations

import re
from collections import Counter

# Bounded quantifiers: an unbounded `[\w.+-]+@` backtracks quadratically over a
# long non-@ run of word chars (a ReDoS on the arbitrary text parse_cv accepts).
# RFC caps: local part 64, domain label 255, TLD is short. Linear at any size.
_EMAIL_RE = re.compile(r"[\w.+-]{1,64}@[\w-]{1,255}\.[a-zA-Z]{2,24}")
_PHONE_RE = re.compile(r"[+\d][\d\s\-()]{6,24}")
_URL_RE = re.compile(r"https?://\S+")

# A CV over this size is pathological, not a résumé — the parse_cv tool rejects it.
MAX_CV_CHARS = 200_000
_MAX_SKILLS_TOP = 12
_LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/\S+", re.IGNORECASE)
_GITHUB_RE = re.compile(r"https?://(?:www\.)?github\.com/\S+", re.IGNORECASE)
_NAME_LABEL_RE = re.compile(r"^\s*name\s*[:\-]\s*(.+)$", re.IGNORECASE)
_SECTION_HEADER_RE = re.compile(
    r"^\s*(EXPERIENCE|EDUCATION|SKILLS|WORK|SUMMARY|PROFILE|PROJECTS|ABOUT)\b", re.IGNORECASE
)

# Evidence-only modality → existing WorkMode / EmploymentType enums.
# Patterns are bounded; matches must be word-ish (not inventing from noise).
_WORK_MODE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("remote", re.compile(r"\b(?:remote|wfh)\b", re.IGNORECASE)),
    ("hybrid", re.compile(r"\bhybrid\b", re.IGNORECASE)),
    ("onsite", re.compile(r"\b(?:on[\s\-]?site|onsite)\b", re.IGNORECASE)),
)
_EMPLOYMENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("contract", re.compile(r"\bcontract(?:ing|or|s)?\b", re.IGNORECASE)),
    ("freelance", re.compile(r"\bfree[\s\-]?lanc(?:e|er|ing)\b", re.IGNORECASE)),
    ("full_time", re.compile(r"\bfull[\s\-]?time\b", re.IGNORECASE)),
    ("part_time", re.compile(r"\bpart[\s\-]?time\b", re.IGNORECASE)),
)
# Not EmploymentType enums — surface as signals only.
_SIGNAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("b2b", re.compile(r"\bb2b\b", re.IGNORECASE)),
    ("invoice", re.compile(r"\binvoice(?:able|s|d)?\b", re.IGNORECASE)),
)

# YAGNI-sized tech allowlist — whole-word hits only; never free-text invention.
_SKILL_ALLOWLIST: frozenset[str] = frozenset(
    {
        "python",
        "fastapi",
        "django",
        "flask",
        "llm",
        "llms",
        "mcp",
        "langchain",
        "langgraph",
        "agents",
        "agentic",
        "openai",
        "anthropic",
        "transformers",
        "pytorch",
        "tensorflow",
        "numpy",
        "pandas",
        "docker",
        "kubernetes",
        "k8s",
        "aws",
        "gcp",
        "azure",
        "terraform",
        "postgres",
        "postgresql",
        "sqlite",
        "redis",
        "rabbitmq",
        "kafka",
        "graphql",
        "rest",
        "grpc",
        "typescript",
        "javascript",
        "node",
        "react",
        "nextjs",
        "rust",
        "go",
        "golang",
        "java",
        "kotlin",
        "swift",
        "rag",
        "vector",
        "embeddings",
        "chromadb",
        "pinecone",
        "weaviate",
        "pytest",
        "cicd",
        "github",
        "gitlab",
        "linux",
        "bash",
        "sql",
        "nosql",
        "spark",
        "airflow",
        "mlops",
        "ml",
        "nlp",
        "cv",
        "vision",
        "selenium",
        "playwright",
    }
)
# Precompiled whole-word patterns per allowlisted skill (bounded token).
_SKILL_RES: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (skill, re.compile(rf"\b{re.escape(skill)}\b", re.IGNORECASE))
    for skill in sorted(_SKILL_ALLOWLIST)
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


def _extract_setup_hints(cv_text: str) -> dict:
    """Evidence-only setup focus. Empty lists = unknown; never invent titles."""
    work_modes: list[str] = []
    employment_types: list[str] = []
    signals: list[str] = []

    for mode, pattern in _WORK_MODE_PATTERNS:
        if pattern.search(cv_text):
            work_modes.append(mode)
            signals.append(f"keyword: {mode}")
    for emp, pattern in _EMPLOYMENT_PATTERNS:
        if pattern.search(cv_text):
            employment_types.append(emp)
            signals.append(f"keyword: {emp}")
    for label, pattern in _SIGNAL_PATTERNS:
        if pattern.search(cv_text):
            signals.append(f"keyword: {label}")

    counts: Counter[str] = Counter()
    for skill, pattern in _SKILL_RES:
        n = len(pattern.findall(cv_text))
        if n:
            # Normalize plural-ish aliases to a canonical display token.
            canonical = {
                "llms": "llm",
                "postgresql": "postgres",
                "golang": "go",
                "k8s": "kubernetes",
            }.get(skill, skill)
            counts[canonical] += n

    skills_top = [
        skill
        for skill, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[
            :_MAX_SKILLS_TOP
        ]
    ]

    return {
        "work_modes": work_modes,
        "employment_types": employment_types,
        "skills_top": skills_top,
        "signals": signals,
    }


def extract_profile_from_cv(cv_text: str) -> dict:
    """Parse CV text into profile-shaped fields. None / [] = low confidence."""
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
        "setup_hints": _extract_setup_hints(cv_text),
        "cv_text": cv_text,
    }
