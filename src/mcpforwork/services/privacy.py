"""GDPR data-subject rights: export (portability) and delete (erasure).

Both walk the SAME ordered `_USER_TABLES` constant so they can never drift.
`audit_log` is deliberately NOT FORCE-RLS'd (it is cross-cutting), so every read
here filters by `user_id` explicitly — the S1-gate carried requirement.
"""

from __future__ import annotations

from typing import Any

from mcpforwork import config
from mcpforwork.ports.db import UnitOfWork
from mcpforwork.services.briefs import ASSET_TYPES

# Per-user tables in FK-safe child -> parent DELETE order (findings are a parent
# of applications/generated_assets/external_applications, so they come after).
# A trusted, code-defined identifier list — never user input — so interpolating
# a name into the statement is safe (SQL identifiers cannot be parameterized).
# `users` is the root, handled separately (scoped by `id`, deleted last).
_USER_TABLES: tuple[str, ...] = (
    "sessions",
    "audit_log",
    "autopilot_policy",
    "playbook_reports",
    "applications",
    "generated_assets",
    "external_applications",
    "explore_findings",
    "style_profile",
    "achievements",
    "profiles",
)

# Auth-internal tables that reference users(id): ERASED on delete (so a logged-in
# account has no orphaned rows / FK failure) but NOT included in the portability
# export — a hash of a single-use credential is internal auth state, not user
# content the subject provided.
_AUTH_TABLES: tuple[str, ...] = ("magic_link_tokens",)


def export_user_data(uow: UnitOfWork, user_id: int) -> dict[str, Any]:
    """Every row this user owns, across all per-user tables plus the `users`
    row — read-only and JSON-serializable (data portability)."""
    user = uow.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
    export: dict[str, Any] = {"user": dict(user) if user else None}
    for table in _USER_TABLES:
        rows = uow.fetchall(f"SELECT * FROM {table} WHERE user_id = ? ORDER BY id", (user_id,))
        export[table] = [dict(row) for row in rows]
    return export


def _erase_asset_files(uow: UnitOfWork, user_id: int) -> int:
    """Delete any on-disk asset files `get_asset_file` materialized for this user
    (self-host copies of CV/cover content under data_dir/assets). Scoped to the
    user's OWN generated_assets, so it is safe on shared/multi-tenant storage —
    it never touches another tenant's files. Matches get_asset_file's naming."""
    directory = config.data_dir() / "assets"
    removed = 0
    for row in uow.fetchall(
        "SELECT id, asset_type FROM generated_assets WHERE user_id = ?", (user_id,)
    ):
        if row["asset_type"] not in ASSET_TYPES:  # read-side whitelist (defense in depth)
            continue
        path = directory / f"{row['id']}_{row['asset_type']}.md"
        if path.exists():
            path.unlink()
            removed += 1
    return removed


def delete_user_data(uow: UnitOfWork, user_id: int) -> dict[str, Any]:
    """Erase every row this user owns, the on-disk asset files, then the `users`
    row (right to erasure) — so the tool's "nothing is kept" is literally true.

    Child → parent order keeps foreign keys satisfied. Returns per-table delete
    counts; the caller commits. No audit row is written: the user's audit_log is
    itself erased and a post-delete row would reference a deleted user — erasure
    is meant to leave no trace."""
    asset_files_removed = _erase_asset_files(uow, user_id)  # before the rows vanish
    deleted: dict[str, int] = {}
    for table in (*_USER_TABLES, *_AUTH_TABLES):
        cursor = uow.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        deleted[table] = cursor.rowcount if cursor.rowcount is not None else 0
    cursor = uow.execute("DELETE FROM users WHERE id = ?", (user_id,))
    deleted["users"] = cursor.rowcount if cursor.rowcount is not None else 0
    return {"ok": True, "deleted": deleted, "asset_files_removed": asset_files_removed}
