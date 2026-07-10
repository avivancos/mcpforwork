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
        for field in domain.PRIVATE_SALARY_FIELDS:
            facts.pop(field, None)
    return facts
