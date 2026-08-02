"""GDPR data-subject rights (S6.4): export_user_data (portability) and
delete_user_data (erasure). Also closes the S1-gate carried item — audit_log is
not FORCE-RLS'd, so its per-tenant rows (applied URLs) must never leak across
users on any read path."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mcpforwork.adapters.db import connect
from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.entrypoints.mcp import server
from mcpforwork.services import apply as apply_service
from mcpforwork.services import (
    assets,
    auth_session,
    autopilot,
    hunt,
    playbooks,
    privacy,
    profiles,
    review,
)

# Every per-user table must be represented, so export/delete completeness is real.
_PER_USER_TABLES = {
    "profiles",
    "achievements",
    "style_profile",
    "explore_findings",
    "external_applications",
    "generated_assets",
    "applications",
    "playbook_reports",
    "audit_log",
    "autopilot_policy",
    "sessions",
}


def _populate(uow: SqlUnitOfWork, email: str, url: str) -> tuple[int, int]:
    """Seed a user with at least one row in EVERY per-user table."""
    uid = uow.insert("INSERT INTO users (email) VALUES (?)", (email,))
    pid = profiles.create_profile(
        uow,
        uid,
        {"full_name": "Ada", "contact_email": email, "target_titles": ["Data Engineer"]},
    )
    profiles.add_achievements(uow, uid, pid, [{"metric": "Cut latency 40%"}])
    profiles.set_style_profile(uow, uid, pid, "I write plainly.")
    hunt.submit_findings(uow, uid, "weworkremotely", [{"url": url, "title": "Data Engineer"}])
    fid = hunt.list_matches(uow, uid, min_score=0)[0]["id"]
    review.approve_match(uow, uid, fid)
    assets.submit_asset(uow, uid, fid, "cv", "# CV")
    session = apply_service.start_application(uow, uid, fid)
    app_id = session["application_id"]
    for step in session["steps"]:
        apply_service.report_apply_progress(uow, uid, app_id, step["step_id"], "ok")
    apply_service.request_submit(uow, uid, app_id)
    apply_service.confirm_submitted(uow, uid, app_id)  # writes external_applications + audit
    playbooks.report_playbook_result(uow, uid, "weworkremotely", "success", {"ok": 1})
    autopilot.put_policy(uow, uid, min_score=70, max_per_day=2)  # autopilot_policy row
    auth_session.issue_session(
        uow, uid, secret="privacy-test-secret", now=datetime.now(UTC)
    )  # sessions row
    uow.commit()
    return uid, fid


def test_export_gathers_every_per_user_table(uow: SqlUnitOfWork) -> None:
    uid, _ = _populate(uow, "a@example.com", "https://x.com/jobs/1")
    export = privacy.export_user_data(uow, uid)
    assert export["user"]["email"] == "a@example.com"
    for table in _PER_USER_TABLES:
        assert export[table], f"{table} missing from export"
    # JSON-serializable end to end (the tool returns JSON).
    assert json.dumps(export, default=str)


def test_export_never_leaks_another_users_rows(uow: SqlUnitOfWork) -> None:
    a, _ = _populate(uow, "a@example.com", "https://a.com/jobs/1")
    _b, _ = _populate(uow, "b@example.com", "https://b-secret.com/jobs/9")
    export = privacy.export_user_data(uow, a)
    blob = json.dumps(export, default=str)
    assert "b-secret.com" not in blob  # B's finding + audit-logged applied URL
    assert "b@example.com" not in blob
    # Every returned row is A's.
    for table in _PER_USER_TABLES:
        assert all(row["user_id"] == a for row in export[table])


def test_export_audit_log_is_user_scoped(uow: SqlUnitOfWork) -> None:
    # The carried S1-gate item: audit_log is not FORCE-RLS'd; the read path must
    # filter by user_id or B's applied URLs leak into A's export.
    a, _ = _populate(uow, "a@example.com", "https://a.com/jobs/1")
    b, _ = _populate(uow, "b@example.com", "https://b.com/jobs/2")
    a_audit = privacy.export_user_data(uow, a)["audit_log"]
    assert a_audit and all(row["user_id"] == a for row in a_audit)


def test_delete_removes_all_of_a_users_rows(uow: SqlUnitOfWork) -> None:
    uid, _ = _populate(uow, "a@example.com", "https://a.com/jobs/1")
    result = privacy.delete_user_data(uow, uid)
    uow.commit()
    assert result["ok"] is True
    for table in _PER_USER_TABLES:
        assert (
            uow.fetchone(f"SELECT COUNT(*) AS n FROM {table} WHERE user_id = ?", (uid,))["n"] == 0
        )
    assert uow.fetchone("SELECT id FROM users WHERE id = ?", (uid,)) is None  # root gone
    assert sum(result["deleted"].values()) >= len(_PER_USER_TABLES)  # counted every table


def test_delete_leaves_other_users_untouched(uow: SqlUnitOfWork) -> None:
    a, _ = _populate(uow, "a@example.com", "https://a.com/jobs/1")
    b, _ = _populate(uow, "b@example.com", "https://b.com/jobs/2")
    privacy.delete_user_data(uow, a)
    uow.commit()
    assert uow.fetchone("SELECT id FROM users WHERE id = ?", (b,)) is not None
    for table in _PER_USER_TABLES:
        assert uow.fetchone(f"SELECT COUNT(*) AS n FROM {table} WHERE user_id = ?", (b,))["n"] >= 1


def test_delete_erases_on_disk_asset_files(uow: SqlUnitOfWork, tmp_path: Path, monkeypatch) -> None:
    # The tool promises "nothing is kept" — the materialized CV file must go too.
    monkeypatch.setenv("MCPFORWORK_DATA_DIR", str(tmp_path / "data"))
    uid, fid = _populate(uow, "a@example.com", "https://a.com/jobs/1")
    aid = uow.fetchone("SELECT id FROM generated_assets WHERE user_id = ? LIMIT 1", (uid,))["id"]
    written = apply_service.get_asset_file(uow, uid, aid)["path"]
    assert Path(written).is_file()  # materialized on disk

    result = privacy.delete_user_data(uow, uid)
    uow.commit()
    assert not Path(written).exists()  # erased
    assert result["asset_files_removed"] >= 1


def test_export_and_delete_of_a_nonexistent_user_do_not_crash(uow: SqlUnitOfWork) -> None:
    export = privacy.export_user_data(uow, 999999)
    assert export["user"] is None
    assert all(export[table] == [] for table in _PER_USER_TABLES)
    result = privacy.delete_user_data(uow, 999999)  # nothing to erase
    uow.commit()
    assert result["ok"] is True
    assert sum(result["deleted"].values()) == 0


def test_delete_erases_a_users_magic_link_tokens(uow: SqlUnitOfWork) -> None:
    # Regression: magic_link_tokens (S6.1a) has an FK to users, so erasure must
    # clear it too or the final DELETE FROM users hits the constraint. This is
    # the auth-internal erase path a logged-in account hits.
    from datetime import UTC, datetime

    from mcpforwork.services import auth_session

    req = auth_session.request_magic_link(
        uow, "ada@example.com", now=datetime(2026, 1, 1, tzinfo=UTC)
    )
    uid = req["user_id"]
    uow.commit()
    n = uow.fetchone("SELECT COUNT(*) AS n FROM magic_link_tokens WHERE user_id = ?", (uid,))["n"]
    assert n == 1
    assert privacy.delete_user_data(uow, uid)["ok"] is True
    uow.commit()
    gone = uow.fetchone("SELECT COUNT(*) AS n FROM magic_link_tokens WHERE user_id = ?", (uid,))[
        "n"
    ]
    assert gone == 0
    assert uow.fetchone("SELECT id FROM users WHERE id = ?", (uid,)) is None  # no FK failure


def test_delete_is_idempotent(uow: SqlUnitOfWork) -> None:
    uid, _ = _populate(uow, "a@example.com", "https://a.com/jobs/1")
    privacy.delete_user_data(uow, uid)
    uow.commit()
    again = privacy.delete_user_data(uow, uid)  # nothing left
    uow.commit()
    assert again["ok"] is True
    assert sum(again["deleted"].values()) == 0


def test_request_deletion_summarizes_and_mints_a_token_without_deleting(
    uow: SqlUnitOfWork,
) -> None:
    uid, _ = _populate(uow, "a@example.com", "https://x.com/jobs/1")
    result = privacy.request_deletion(uow, uid)
    uow.commit()
    # The summary tells the human exactly what erasure means, per table.
    assert result["summary"]["profiles"] == 1
    assert result["summary"]["applications"] == 1
    assert result["summary"]["users"] == 1
    assert result["expires_in_seconds"] == 300
    assert len(result["confirm_token"]) >= 32
    # Nothing deleted; the request itself is on the audit trail.
    assert uow.fetchone("SELECT id FROM users WHERE id = ?", (uid,)) is not None
    assert uow.fetchone(
        "SELECT id FROM audit_log WHERE user_id = ? AND action = 'delete_my_data_requested'",
        (uid,),
    )
    # Only the HASH is stored — the raw token is never persisted.
    stored = uow.fetchone("SELECT token_hash FROM delete_confirm_tokens WHERE user_id = ?", (uid,))
    assert stored and stored["token_hash"] != result["confirm_token"]


def test_execute_deletion_with_a_valid_token_erases_everything(uow: SqlUnitOfWork) -> None:
    uid, _ = _populate(uow, "a@example.com", "https://x.com/jobs/1")
    token = privacy.request_deletion(uow, uid)["confirm_token"]
    uow.commit()
    result = privacy.execute_deletion(uow, uid, token)
    uow.commit()
    assert result["ok"] is True
    for table in _PER_USER_TABLES:
        assert (
            uow.fetchone(f"SELECT COUNT(*) AS n FROM {table} WHERE user_id = ?", (uid,))["n"] == 0
        )
    assert uow.fetchone("SELECT id FROM users WHERE id = ?", (uid,)) is None


def test_execute_deletion_rejects_an_unknown_token_and_deletes_nothing(
    uow: SqlUnitOfWork,
) -> None:
    uid, _ = _populate(uow, "a@example.com", "https://x.com/jobs/1")
    result = privacy.execute_deletion(uow, uid, "not-a-real-token")
    uow.commit()
    assert result["kind"] == "invalid_token"
    assert uow.fetchone("SELECT id FROM users WHERE id = ?", (uid,)) is not None
    assert uow.fetchone("SELECT COUNT(*) AS n FROM profiles WHERE user_id = ?", (uid,))["n"] == 1


def test_execute_deletion_rejects_a_reused_token(uow: SqlUnitOfWork) -> None:
    # Single-use: the second execution with the same token must fail even
    # though the first already erased the user (the token row is gone too) —
    # and a FRESH user's token from the same flow must not be replayable.
    uid, _ = _populate(uow, "a@example.com", "https://x.com/jobs/1")
    token = privacy.request_deletion(uow, uid)["confirm_token"]
    uow.commit()
    assert privacy.execute_deletion(uow, uid, token)["ok"] is True
    uow.commit()
    again = privacy.execute_deletion(uow, uid, token)
    assert again["kind"] == "invalid_token"  # row erased with the account


def test_execute_deletion_erases_its_own_token_rows(uow: SqlUnitOfWork) -> None:
    # FK-safe erasure: the token rows vanish with the account, so the final
    # DELETE FROM users cannot hit the delete_confirm_tokens constraint.
    uid, _ = _populate(uow, "a@example.com", "https://x.com/jobs/1")
    token = privacy.request_deletion(uow, uid)["confirm_token"]
    uow.commit()
    privacy.execute_deletion(uow, uid, token)
    uow.commit()
    assert (
        uow.fetchone("SELECT COUNT(*) AS n FROM delete_confirm_tokens WHERE user_id = ?", (uid,))[
            "n"
        ]
        == 0
    )


def test_execute_deletion_rejects_an_expired_token(uow: SqlUnitOfWork) -> None:
    uid, _ = _populate(uow, "a@example.com", "https://x.com/jobs/1")
    t0 = datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC)
    token = privacy.request_deletion(uow, uid, now=t0)["confirm_token"]
    uow.commit()
    later = datetime(2026, 8, 2, 12, 6, 0, tzinfo=UTC)  # 6 min > 5 min TTL
    result = privacy.execute_deletion(uow, uid, token, now=later)
    uow.commit()
    assert result["kind"] == "token_expired"
    assert uow.fetchone("SELECT id FROM users WHERE id = ?", (uid,)) is not None


def test_the_token_expires_at_exactly_its_ttl_boundary(uow: SqlUnitOfWork) -> None:
    # Boundary pin: at exactly expires_at the token is already expired (>=),
    # one second before it still redeems.
    uid, _ = _populate(uow, "a@example.com", "https://x.com/jobs/1")
    t0 = datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC)
    boundary = datetime.fromtimestamp(
        int(t0.timestamp()) + privacy.CONFIRM_TOKEN_TTL_SECONDS, tz=UTC
    )
    expired = privacy.request_deletion(uow, uid, now=t0)["confirm_token"]
    assert privacy.execute_deletion(uow, uid, expired, now=boundary)["kind"] == "token_expired"
    fresh = privacy.request_deletion(uow, uid, now=t0)["confirm_token"]
    uow.commit()
    just_before = datetime.fromtimestamp(boundary.timestamp() - 1, tz=UTC)
    result = privacy.execute_deletion(uow, uid, fresh, now=just_before)
    uow.commit()
    assert result["ok"] is True
    assert result["audited_as"] == "delete_my_data_confirmed"


def test_execute_deletion_refuses_another_users_token(uow: SqlUnitOfWork) -> None:
    # Cross-tenant: B's token presented as A must refuse WITHOUT revealing
    # the token exists (same error as unknown) and delete nothing of anyone's.
    a, _ = _populate(uow, "a@example.com", "https://a.com/jobs/1")
    b, _ = _populate(uow, "b@example.com", "https://b.com/jobs/2")
    b_token = privacy.request_deletion(uow, b)["confirm_token"]
    uow.commit()
    result = privacy.execute_deletion(uow, a, b_token)
    uow.commit()
    assert result["kind"] == "invalid_token"
    for uid in (a, b):
        assert uow.fetchone("SELECT id FROM users WHERE id = ?", (uid,)) is not None


def test_delete_my_data_tool_is_two_step(mcp_env) -> None:
    server.update_profile(
        {"full_name": "Ada", "contact_email": "ada@x.com", "target_titles": ["Data Engineer"]}
    )
    step1 = json.loads(server.delete_my_data())
    assert step1["summary"]["profiles"] == 1 and step1["confirm_token"]
    # Nothing deleted by step 1.
    fresh = connect(mcp_env)
    try:
        assert fresh.fetchone("SELECT COUNT(*) AS n FROM profiles WHERE user_id = 1")["n"] == 1
    finally:
        fresh.close()
    step2 = json.loads(server.delete_my_data(confirm_token=step1["confirm_token"]))
    assert step2["ok"] is True
    fresh = connect(mcp_env)
    try:
        assert fresh.fetchone("SELECT id FROM users WHERE id = 1") is None
    finally:
        fresh.close()


def test_delete_my_data_tool_has_no_boolean_confirm_path(mcp_env) -> None:
    # Structural: the pre-S7.2d boolean gate is gone — an agent cannot erase
    # with `confirm=True` alone; the parameter no longer exists.
    import inspect

    params = inspect.signature(server.delete_my_data).parameters
    assert "confirm" not in params
    assert "confirm_token" in params
    with pytest.raises(TypeError):
        server.delete_my_data(confirm=True)


def test_export_and_delete_tools_roundtrip_on_fresh_connection(mcp_env) -> None:
    server.update_profile(
        {"full_name": "Ada", "contact_email": "ada@x.com", "target_titles": ["Data Engineer"]}
    )
    export = json.loads(server.export_my_data())
    assert export["user"]["email"] and export["profiles"]

    token = json.loads(server.delete_my_data())["confirm_token"]
    confirmed = json.loads(server.delete_my_data(confirm_token=token))
    assert confirmed["ok"] is True
    fresh = connect(mcp_env)
    try:
        assert fresh.fetchone("SELECT id FROM users WHERE id = 1") is None
        assert fresh.fetchone("SELECT COUNT(*) AS n FROM profiles WHERE user_id = 1")["n"] == 0
    finally:
        fresh.close()


def test_privacy_tools_are_registered() -> None:
    import asyncio

    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert {"export_my_data", "delete_my_data"} <= names
