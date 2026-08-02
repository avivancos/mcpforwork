"""GDPR data-subject rights (S6.4): export_user_data (portability) and
delete_user_data (erasure). Also closes the S1-gate carried item — audit_log is
not FORCE-RLS'd, so its per-tenant rows (applied URLs) must never leak across
users on any read path."""

import json
from datetime import UTC, datetime
from pathlib import Path

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


def test_delete_my_data_tool_refuses_without_confirm(mcp_env) -> None:
    server.update_profile(
        {"full_name": "Ada", "contact_email": "ada@x.com", "target_titles": ["Data Engineer"]}
    )
    refusal = json.loads(server.delete_my_data(confirm=False))
    assert "error" in refusal
    assert "confirm" in refusal["error"].lower()  # names the guard, not a generic error
    # Data still there on a fresh connection — the refusal did not delete.
    fresh = connect(mcp_env)
    try:
        assert fresh.fetchone("SELECT COUNT(*) AS n FROM profiles WHERE user_id = 1")["n"] == 1
    finally:
        fresh.close()


def test_export_and_delete_tools_roundtrip_on_fresh_connection(mcp_env) -> None:
    server.update_profile(
        {"full_name": "Ada", "contact_email": "ada@x.com", "target_titles": ["Data Engineer"]}
    )
    export = json.loads(server.export_my_data())
    assert export["user"]["email"] and export["profiles"]

    confirmed = json.loads(server.delete_my_data(confirm=True))
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
