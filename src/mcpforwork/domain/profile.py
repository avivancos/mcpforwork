"""Profile domain: intake enums, tier definitions, and validation.

Pure logic — no I/O, no other layer. The intake model is sector- and
country-agnostic BY DATA: target titles and sectors are user-supplied values,
never hardcoded personas. The service layer (de)serializes JSON fields and
persists; this module only decides what is valid and what is private.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum, StrEnum

MAX_TARGET_TITLES = 5


class Seniority(StrEnum):
    ENTRY = "entry"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXEC = "exec"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    CONTRACT = "contract"
    PART_TIME = "part_time"
    FREELANCE = "freelance"


class WorkMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"


class SalaryPeriod(StrEnum):
    YEAR = "year"
    MONTH = "month"
    DAY = "day"
    HOUR = "hour"


# Fields the service must never place in a generation brief without explicit
# consent (§4 never-fabricate / privacy). Minimum salary is a deal-breaker
# filter, never disclosed in materials without the candidate saying so.
PRIVATE_SALARY_FIELDS: tuple[str, ...] = (
    "min_salary_amount",
    "min_salary_currency",
    "min_salary_period",
)

# Persisted profile fields stored as JSON text (lists / dicts) vs scalar columns.
JSON_FIELDS: frozenset[str] = frozenset(
    {
        "work_auth_countries",
        "target_titles",
        "sectors",
        "employment_types",
        "work_modes",
        "languages",
        "links",
        "deal_breakers",
    }
)
SCALAR_FIELDS: frozenset[str] = frozenset(
    {
        "label",
        "full_name",
        "contact_email",
        "country",
        "city",
        "needs_sponsorship",
        "seniority",
        "relocation",
        "min_salary_amount",
        "min_salary_currency",
        "min_salary_period",
        "cv_text",
        "availability_date",
        "notice_period",
        "career_narrative",
        "salary_public_amount",
        "salary_public_currency",
        "negotiation_floor",
    }
)
EDITABLE_FIELDS: frozenset[str] = JSON_FIELDS | SCALAR_FIELDS

_ENUM_FIELDS: dict[str, type[Enum]] = {"seniority": Seniority, "min_salary_period": SalaryPeriod}
_ENUM_LIST_FIELDS: dict[str, type[Enum]] = {
    "employment_types": EmploymentType,
    "work_modes": WorkMode,
}


class ProfileValidationError(ValueError):
    """A profile create/update payload violated the intake contract."""


def _valid_values(enum: type[Enum]) -> set[str]:
    return {member.value for member in enum}


def validate_patch(patch: Mapping[str, object]) -> None:
    """Validate a partial profile payload. Only keys present are checked, so it
    serves both create and update. Raises `ProfileValidationError` on the first
    violation."""
    for key in patch:
        if key not in EDITABLE_FIELDS:
            raise ProfileValidationError(f"unknown profile field: {key!r}")

    for field, enum in _ENUM_FIELDS.items():
        if patch.get(field) is not None and patch[field] not in _valid_values(enum):
            raise ProfileValidationError(
                f"{field} must be one of {sorted(_valid_values(enum))}, got {patch[field]!r}"
            )

    for field, enum in _ENUM_LIST_FIELDS.items():
        value = patch.get(field)
        if value is None:
            continue
        if not isinstance(value, list):
            raise ProfileValidationError(f"{field} must be a list")
        invalid = [v for v in value if v not in _valid_values(enum)]
        if invalid:
            raise ProfileValidationError(
                f"{field} has invalid values {invalid}; allowed {sorted(_valid_values(enum))}"
            )

    titles = patch.get("target_titles")
    if titles is not None:
        if not isinstance(titles, list) or not titles:
            raise ProfileValidationError("target_titles must be a non-empty list")
        if len(titles) > MAX_TARGET_TITLES:
            raise ProfileValidationError(f"target_titles accepts at most {MAX_TARGET_TITLES}")
