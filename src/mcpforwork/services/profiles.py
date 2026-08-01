"""Profile use cases.

Signatures are `(uow, user_id, ...)`; the caller owns the transaction. Every
query is scoped by `user_id` — the app-level isolation that self-host SQLite
relies on, and defense-in-depth alongside Postgres RLS. JSON list/dict fields
are (de)serialized here so callers work in plain Python.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from mcpforwork.domain import profile as domain
from mcpforwork.ports.db import Row, UnitOfWork


def _serialize(field: str, value: Any) -> Any:
    return json.dumps(value) if field in domain.JSON_FIELDS and value is not None else value


def _deserialize(row: Row) -> Row:
    out = dict(row)
    for field in domain.JSON_FIELDS:
        if out.get(field) is not None:
            out[field] = json.loads(out[field])
    return out


def _require_owned_profile(uow: UnitOfWork, user_id: int, profile_id: int) -> None:
    """Reject writes targeting a profile the user does not own — so a child row
    (achievement, style) can never be stamped onto a foreign profile."""
    if (
        uow.fetchone("SELECT id FROM profiles WHERE id = ? AND user_id = ?", (profile_id, user_id))
        is None
    ):
        raise domain.ProfileValidationError(f"profile {profile_id} not found for this user")


def create_profile(
    uow: UnitOfWork,
    user_id: int,
    data: Mapping[str, Any] | None = None,
    *,
    label: str = "default",
    make_active: bool = True,
) -> int:
    """Create a profile for `user_id` and return its id. When `make_active`,
    any previously active profile for the user is deactivated first (one active
    profile per user)."""
    payload = dict(data or {})
    payload.pop("label", None)  # label is set explicitly, not via the data map
    domain.validate_patch(payload)

    if make_active:
        uow.execute("UPDATE profiles SET is_active = 0 WHERE user_id = ?", (user_id,))

    columns = ["user_id", "label", "is_active"]
    values: list[Any] = [user_id, label, 1 if make_active else 0]
    for field, value in payload.items():
        columns.append(field)
        values.append(_serialize(field, value))
    placeholders = ", ".join(["?"] * len(values))
    return uow.insert(
        f"INSERT INTO profiles ({', '.join(columns)}) VALUES ({placeholders})", values
    )


def get_profile(uow: UnitOfWork, user_id: int, profile_id: int | None = None) -> Row | None:
    """Return the profile as a plain dict (JSON fields parsed). With no
    `profile_id`, returns the user's active profile."""
    if profile_id is None:
        row = uow.fetchone("SELECT * FROM profiles WHERE user_id = ? AND is_active = 1", (user_id,))
    else:
        row = uow.fetchone(
            "SELECT * FROM profiles WHERE user_id = ? AND id = ?", (user_id, profile_id)
        )
    return _deserialize(row) if row is not None else None


def list_profiles(uow: UnitOfWork, user_id: int) -> list[Row]:
    rows = uow.fetchall("SELECT * FROM profiles WHERE user_id = ? ORDER BY id", (user_id,))
    return [_deserialize(r) for r in rows]


def update_profile(
    uow: UnitOfWork, user_id: int, profile_id: int, patch: Mapping[str, Any]
) -> None:
    """Apply a partial update. Validated against the intake contract; unknown
    fields are rejected."""
    domain.validate_patch(patch)
    if not patch:
        return
    assignments = []
    values: list[Any] = []
    for field, value in patch.items():
        assignments.append(f"{field} = ?")
        values.append(_serialize(field, value))
    values.extend([user_id, profile_id])
    uow.execute(
        f"UPDATE profiles SET {', '.join(assignments)} WHERE user_id = ? AND id = ?", values
    )


def set_active_profile(uow: UnitOfWork, user_id: int, profile_id: int) -> None:
    uow.execute("UPDATE profiles SET is_active = 0 WHERE user_id = ?", (user_id,))
    uow.execute(
        "UPDATE profiles SET is_active = 1 WHERE user_id = ? AND id = ?", (user_id, profile_id)
    )


def add_achievements(
    uow: UnitOfWork, user_id: int, profile_id: int, items: Sequence[Mapping[str, Any]]
) -> list[int]:
    """Append quantified wins to the achievements bank; returns the new ids."""
    _require_owned_profile(uow, user_id, profile_id)
    ids: list[int] = []
    for item in items:
        if not item.get("metric"):
            raise domain.ProfileValidationError("each achievement needs a 'metric'")
        ids.append(
            uow.insert(
                "INSERT INTO achievements (user_id, profile_id, metric, context, role)"
                " VALUES (?, ?, ?, ?, ?)",
                (user_id, profile_id, item["metric"], item.get("context"), item.get("role")),
            )
        )
    return ids


def list_achievements(uow: UnitOfWork, user_id: int, profile_id: int) -> list[Row]:
    return uow.fetchall(
        "SELECT * FROM achievements WHERE user_id = ? AND profile_id = ? ORDER BY id",
        (user_id, profile_id),
    )


def set_style_profile(
    uow: UnitOfWork,
    user_id: int,
    profile_id: int,
    writing_sample: str,
    directives: Mapping[str, Any] | None = None,
) -> None:
    """Upsert the profile's style profile (one per profile)."""
    _require_owned_profile(uow, user_id, profile_id)
    encoded = json.dumps(directives) if directives is not None else None
    existing = uow.fetchone(
        "SELECT id FROM style_profile WHERE user_id = ? AND profile_id = ?",
        (user_id, profile_id),
    )
    if existing is not None:
        uow.execute(
            "UPDATE style_profile SET writing_sample = ?, directives = ? WHERE id = ?",
            (writing_sample, encoded, existing["id"]),
        )
    else:
        uow.insert(
            "INSERT INTO style_profile (user_id, profile_id, writing_sample, directives)"
            " VALUES (?, ?, ?, ?)",
            (user_id, profile_id, writing_sample, encoded),
        )


def get_style_profile(uow: UnitOfWork, user_id: int, profile_id: int) -> Row | None:
    row = uow.fetchone(
        "SELECT * FROM style_profile WHERE user_id = ? AND profile_id = ?",
        (user_id, profile_id),
    )
    if row is None:
        return None
    out = dict(row)
    if out.get("directives") is not None:
        out["directives"] = json.loads(out["directives"])
    return out


# Progressive-profiling catalogue: (field, tier, why it matters). Tier 1 =
# required intake; tier 2 = each unlock measurably improves output.
_GAP_CATALOGUE: tuple[tuple[str, int, str], ...] = (
    ("full_name", 1, "identity on every asset and application"),
    ("contact_email", 1, "identity on every asset and application"),
    ("country", 1, "market selection and legal context"),
    ("work_auth_countries", 1, "the #1 hard filter on both sides"),
    ("target_titles", 1, "drives source selection and scoring"),
    ("sectors", 1, "drives source selection and scoring"),
    ("seniority", 1, "filtering and tone of materials"),
    ("employment_types", 1, "different markets entirely"),
    ("work_modes", 1, "hard filter"),
    ("languages", 1, "filters postings and sets asset language"),
    ("cv_text", 1, "seeds the whole profile"),
    ("achievements", 2, "quantified wins — the single highest-leverage input"),
    ("style_profile", 2, "drafts sound like YOU, not like AI"),
    ("links", 2, "profile enrichment from LinkedIn/GitHub/portfolio"),
    ("deal_breakers", 2, "veto filters and honest fit scoring"),
    ("availability_date", 2, "form answers and recruiter replies"),
)


def profile_gaps(uow: UnitOfWork, user_id: int) -> list[Row]:
    """Missing fields, required (tier 1) first — the progressive /setup data.
    The client offers ONE gap at a time when contextually useful."""
    prof = get_profile(uow, user_id)
    if prof is None:
        return [{"field": "profile", "tier": 1, "why": "no profile yet — run /setup"}]
    gaps: list[Row] = []
    for field, tier, why in _GAP_CATALOGUE:
        if field == "achievements":
            missing = not list_achievements(uow, user_id, prof["id"])
        elif field == "style_profile":
            missing = get_style_profile(uow, user_id, prof["id"]) is None
        else:
            missing = not prof.get(field)
        if missing:
            gaps.append({"field": field, "tier": tier, "why": why})
    return sorted(gaps, key=lambda g: g["tier"])


def export_for_brief(
    uow: UnitOfWork,
    user_id: int,
    profile_id: int | None = None,
    *,
    disclose_salary: bool = False,
) -> Row | None:
    """Profile facts destined for a generation brief. Minimum salary is
    redacted unless `disclose_salary` — the structural privacy gate (§4): the
    client LLM never sees private deal-breaker figures without explicit consent.
    """
    facts = get_profile(uow, user_id, profile_id)
    if facts is None:
        return None
    if not disclose_salary:
        # Only the minimum-salary deal-breaker is classified never-disclose by
        # the intake model. salary_public_* and negotiation_floor are
        # offer-stage figures the candidate opted to share, so they pass
        # through. EEO would be gated here too once it is stored (deferred).
        for field in domain.PRIVATE_SALARY_FIELDS:
            facts.pop(field, None)
    return facts


# --------------------------------------------------------------------------- #
# Web dashboard shape (web/src/lib/api/types.ts Profile)
# --------------------------------------------------------------------------- #
# Display ↔ enum for employment types (the intake model stores enum values).
_EMPLOYMENT_DISPLAY = {
    "full_time": "Full-time",
    "contract": "Contract",
    "part_time": "Part-time",
    "freelance": "Freelance",
}
_EMPLOYMENT_FROM_DISPLAY = {v: k for k, v in _EMPLOYMENT_DISPLAY.items()}

_DEFAULT_WEB_PROFILE: dict[str, Any] = {
    "name": "",
    "email": "",
    "headline": "",
    "targetRole": "",
    "cities": [],
    "workRights": "",
    "salaryFloor": "",
    "workMode": "onsite",
    "languages": "",
    "seniority": "",
    "employmentType": "",
    "achievements": [],
    "styleProfile": None,
    "tier1Step": 1,
}


def get_web_profile(uow: UnitOfWork, user_id: int) -> dict[str, Any]:
    """The dashboard's `Profile` shape. A fresh user gets the default shape
    (tier1Step 1 — onboarding starts); every field is derived from real
    columns, never fabricated."""
    prof = get_profile(uow, user_id)
    if prof is None:
        return dict(_DEFAULT_WEB_PROFILE)
    achievements = list_achievements(uow, user_id, prof["id"])
    style = get_style_profile(uow, user_id, prof["id"])
    tier1_open = any(g["tier"] == 1 for g in profile_gaps(uow, user_id))
    rights = ", ".join(prof.get("work_auth_countries") or [])
    if prof.get("needs_sponsorship"):
        rights = f"{rights} · needs sponsorship" if rights else "Needs sponsorship"
    floor = ""
    if prof.get("min_salary_amount"):
        floor = (
            f"{prof.get('min_salary_currency') or ''}{prof['min_salary_amount']:,}"
            f" / {prof.get('min_salary_period') or 'year'}"
        )
    return {
        "name": prof.get("full_name") or "",
        "email": prof.get("contact_email") or "",
        "headline": prof.get("career_narrative") or "",
        "targetRole": (prof.get("target_titles") or [""])[0],
        "cities": [prof["city"]] if prof.get("city") else [],
        "workRights": rights,
        "salaryFloor": floor,
        "workMode": (prof.get("work_modes") or ["onsite"])[0],
        "languages": " · ".join(prof.get("languages") or []),
        "seniority": prof.get("seniority") or "",
        "employmentType": _EMPLOYMENT_DISPLAY.get((prof.get("employment_types") or [""])[0], ""),
        "achievements": [
            {"id": str(a["id"]), "text": a["metric"], "source": a.get("role") or "Achievement"}
            for a in achievements
        ],
        "styleProfile": "Custom style profile set" if style else None,
        "tier1Step": 2 if tier1_open else 4,
    }


def update_web_profile(uow: UnitOfWork, user_id: int, patch: Mapping[str, Any]) -> dict[str, Any]:
    """Map the dashboard's `Partial<Profile>` onto intake columns and apply it
    (creating the profile on first save). Display-only fields with no intake
    column — workRights, salaryFloor, tier1Step — are ignored by design: never
    add schema for a display field."""
    mapped: dict[str, Any] = {}
    if isinstance(patch.get("name"), str):
        mapped["full_name"] = patch["name"]
    if isinstance(patch.get("email"), str):
        mapped["contact_email"] = patch["email"]
    if isinstance(patch.get("headline"), str):
        mapped["career_narrative"] = patch["headline"]
    if isinstance(patch.get("targetRole"), str) and patch["targetRole"].strip():
        mapped["target_titles"] = [patch["targetRole"].strip()]
    if isinstance(patch.get("seniority"), str) and patch["seniority"]:
        mapped["seniority"] = patch["seniority"].lower()
    if isinstance(patch.get("employmentType"), str) and patch["employmentType"]:
        enum_value = _EMPLOYMENT_FROM_DISPLAY.get(patch["employmentType"])
        if enum_value is None:
            return {"error": f"unknown employmentType {patch['employmentType']!r}"}
        mapped["employment_types"] = [enum_value]
    if isinstance(patch.get("workMode"), str) and patch["workMode"]:
        mapped["work_modes"] = [patch["workMode"]]
    if isinstance(patch.get("languages"), str):
        mapped["languages"] = [s.strip() for s in patch["languages"].split("·") if s.strip()]
    if isinstance(patch.get("cities"), list) and patch["cities"]:
        # The intake model has no target-cities column — keep the first entry
        # in `city` (collapse documented on the S6.6b card).
        mapped["city"] = str(patch["cities"][0])
    if not mapped:
        return {"ok": True, "changed": []}
    try:
        prof = get_profile(uow, user_id)
        if prof is None:
            create_profile(uow, user_id, mapped)
        else:
            update_profile(uow, user_id, prof["id"], mapped)
    except domain.ProfileValidationError as exc:
        return {"error": str(exc)}
    return {"ok": True, "changed": sorted(mapped)}
