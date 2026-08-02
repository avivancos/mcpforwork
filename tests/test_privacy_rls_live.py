"""Live-Postgres: GDPR export/delete tenant isolation (S6.4).

The point of interest is `audit_log`: it is deliberately NOT FORCE-RLS'd, so —
unlike the RLS-forced tables, which filter automatically — nothing but the
service's explicit `WHERE user_id` keeps one tenant's audit rows (and applied
URLs) out of another's export. This is the S1-gate carried item, proven on the
backend where it actually matters.

Requires ``-m live`` and ``TEST_POSTGRES_URL``.
"""

import json

import pytest

import pg_support
from mcpforwork.services import hunt, playbooks, privacy, profiles

pytestmark = pytest.mark.live


@pytest.fixture
def two_users():
    if not pg_support.admin_url():
        pytest.skip("TEST_POSTGRES_URL not set")
    admin = pg_support.admin_connect()
    admin.execute(
        "TRUNCATE delete_confirm_tokens, autopilot_policy, sessions, playbook_reports,"
        " applications, generated_assets, explore_findings,"
        " external_applications, style_profile, achievements, profiles, audit_log, users"
        " RESTART IDENTITY CASCADE"
    )
    admin.insert("INSERT INTO users (email) VALUES (?)", ("alice@example.com",))
    admin.insert("INSERT INTO users (email) VALUES (?)", ("bob@example.com",))
    admin.commit()
    try:
        yield admin
    finally:
        admin.close()


def _seed(conn, user_id: int, url: str) -> None:
    conn.set_user_context(user_id)
    profiles.create_profile(conn, user_id, {"full_name": "X", "target_titles": ["DE"]})
    hunt.submit_findings(conn, user_id, "weworkremotely", [{"url": url, "title": "DE"}])
    playbooks.report_playbook_result(conn, user_id, "weworkremotely", "drift", {"x": user_id})
    conn.commit()


def test_export_does_not_leak_audit_log_across_tenants(two_users) -> None:
    alice = pg_support.app_connect()
    bob = pg_support.app_connect()
    try:
        _seed(alice, 1, "https://alice.com/1")
        _seed(bob, 2, "https://bob-secret.com/9")

        export = privacy.export_user_data(alice, 1)
        blob = json.dumps(export, default=str)
        # audit_log is not RLS-forced — only the explicit WHERE keeps bob out.
        assert export["audit_log"] and all(r["user_id"] == 1 for r in export["audit_log"])
        assert "bob-secret.com" not in blob
    finally:
        alice.close()
        bob.close()


def test_delete_confirm_tokens_are_rls_invisible_across_tenants(two_users) -> None:
    """S7.2d two-step erasure on the backend where RLS is real: Alice's
    confirm token is INVISIBLE in Bob's tenant context (FORCE RLS), so his
    redeem attempt is an invalid_token refusal that deletes nothing; Alice's
    own redeem erases her — and only her."""
    admin = two_users
    alice = pg_support.app_connect()
    bob = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        bob.set_user_context(2)
        token = privacy.request_deletion(alice, 1)["confirm_token"]
        alice.commit()

        refusal = privacy.execute_deletion(bob, 2, token)
        assert refusal["kind"] == "invalid_token"
        bob.rollback()  # nothing was written; end the transaction cleanly

        result = privacy.execute_deletion(alice, 1, token)
        alice.commit()
        assert result["ok"] is True
        assert admin.fetchone("SELECT id FROM users WHERE id = 1") is None
        assert admin.fetchone("SELECT id FROM users WHERE id = 2") is not None
    finally:
        alice.close()
        bob.close()


def test_delete_erases_one_tenant_and_spares_the_other(two_users) -> None:
    admin = two_users
    alice = pg_support.app_connect()
    bob = pg_support.app_connect()
    try:
        _seed(alice, 1, "https://alice.com/1")
        _seed(bob, 2, "https://bob-secret.com/9")

        privacy.delete_user_data(alice, 1)
        alice.commit()

        # admin bypasses RLS — it sees the true post-delete state of every tenant.
        assert admin.fetchall("SELECT id FROM audit_log WHERE user_id = 1") == []
        assert admin.fetchall("SELECT id FROM explore_findings WHERE user_id = 1") == []
        assert admin.fetchone("SELECT id FROM users WHERE id = 1") is None
        # Bob is fully intact.
        assert admin.fetchall("SELECT id FROM audit_log WHERE user_id = 2")
        assert admin.fetchone("SELECT id FROM users WHERE id = 2") is not None
    finally:
        alice.close()
        bob.close()
