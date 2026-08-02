"""GDPR data-subject rights: export (portability) and delete (erasure).

Both walk the SAME ordered `_USER_TABLES` constant so they can never drift.
`audit_log` is deliberately NOT FORCE-RLS'd (it is cross-cutting), so every read
here filters by `user_id` explicitly — the S1-gate carried requirement.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from typing import Any

from mcpforwork import config
from mcpforwork.ports.db import UnitOfWork
from mcpforwork.services import audit
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
_AUTH_TABLES: tuple[str, ...] = ("magic_link_tokens", "delete_confirm_tokens")

# Step-1 → step-2 window for the two-step erasure flow (S7.2d).
CONFIRM_TOKEN_TTL_SECONDS = 300


def _hash_token(raw_token: str) -> str:
    # Same scheme as auth_session._hash_token (sha256 hex, raw never stored).
    # Duplicated deliberately: sharing a private helper across services would
    # couple two modules for one stdlib call.
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def request_deletion(
    uow: UnitOfWork, user_id: int, *, now: datetime | None = None
) -> dict[str, Any]:
    """Step 1 of 2 (S7.2d): summarize what erasure would delete and mint a
    single-use confirm token (5 min TTL, only its hash stored). The token IS
    the consent artifact for destruction — an agent can reach this far, but
    only a human who is shown the token can authorize step 2."""
    now = now or datetime.now(UTC)
    summary: dict[str, int] = {}
    for table in (*_USER_TABLES, *_AUTH_TABLES):
        row = uow.fetchone(f"SELECT COUNT(*) AS n FROM {table} WHERE user_id = ?", (user_id,))
        summary[table] = row["n"] if row else 0
    summary["users"] = 1 if uow.fetchone("SELECT id FROM users WHERE id = ?", (user_id,)) else 0
    raw_token = secrets.token_urlsafe(32)
    uow.execute(
        "INSERT INTO delete_confirm_tokens (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (user_id, _hash_token(raw_token), int(now.timestamp()) + CONFIRM_TOKEN_TTL_SECONDS),
    )
    audit.record(uow, user_id, "delete_my_data_requested", {"tables": sum(summary.values())})
    return {
        "summary": summary,
        "confirm_token": raw_token,
        "expires_in_seconds": CONFIRM_TOKEN_TTL_SECONDS,
    }


def execute_deletion(
    uow: UnitOfWork, user_id: int, confirm_token: str, *, now: datetime | None = None
) -> dict[str, Any]:
    """Step 2 of 2 (S7.2d): redeem a confirm token and erase. Unknown,
    cross-tenant, used, or expired tokens are structured refusals and delete
    NOTHING. The single-use mark is atomic (WHERE used_at IS NULL); the
    execution audit row is written BEFORE the erase, which wipes audit_log."""
    now = now or datetime.now(UTC)
    row = uow.fetchone(
        "SELECT id, user_id, expires_at, used_at FROM delete_confirm_tokens WHERE token_hash = ?",
        (_hash_token(confirm_token),),
    )
    # Unknown and cross-tenant collapse into one refusal: which check failed
    # is never revealed (a valid token's existence is not leaked).
    if row is None or row["user_id"] != user_id:
        return {"error": "invalid confirmation token", "kind": "invalid_token"}
    if row["used_at"] is not None:
        return {"error": "confirmation token already used", "kind": "token_used"}
    if int(now.timestamp()) >= row["expires_at"]:
        return {"error": "confirmation token expired", "kind": "token_expired"}
    cur = uow.execute(
        "UPDATE delete_confirm_tokens SET used_at = ? WHERE id = ? AND used_at IS NULL",
        (int(now.timestamp()), row["id"]),
    )
    if cur.rowcount != 1:  # a concurrent redeem won the flip
        return {"error": "confirmation token already used", "kind": "token_used"}
    # BEFORE the erase: the user's audit_log rows (this one included) vanish
    # with the account, so the confirmation must be recorded first — a crash
    # mid-erase still leaves the consent trace in the transaction log.
    audit.record(uow, user_id, "delete_my_data_confirmed", {})
    result = delete_user_data(uow, user_id)
    result["audited_as"] = "delete_my_data_confirmed"
    return result


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
