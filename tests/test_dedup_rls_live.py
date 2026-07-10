"""Live-Postgres: external_applications enforces tenant isolation through the
dedup service, as the restricted app role.

Requires ``-m live`` and ``TEST_POSTGRES_URL``.
"""

import pytest

import pg_support
from mcpforwork.services import dedup

pytestmark = pytest.mark.live


@pytest.fixture
def two_users():
    if not pg_support.admin_url():
        pytest.skip("TEST_POSTGRES_URL not set")
    admin = pg_support.admin_connect()
    admin.execute(
        "TRUNCATE external_applications, style_profile, achievements, profiles,"
        " audit_log, users RESTART IDENTITY CASCADE"
    )
    admin.insert("INSERT INTO users (email) VALUES (?)", ("alice@example.com",))
    admin.insert("INSERT INTO users (email) VALUES (?)", ("bob@example.com",))
    admin.commit()
    try:
        yield
    finally:
        admin.close()


def test_one_tenants_application_is_invisible_to_another(two_users) -> None:
    alice = pg_support.app_connect()
    bob = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        dedup.record_application(alice, 1, url="https://example.com/jobs/77")
        alice.commit()

        # Bob checking the same URL sees it as new — RLS hides Alice's row.
        bob.set_user_context(2)
        result = dedup.check_seen(bob, 2, ["https://example.com/jobs/77"])
        assert result["items"][0]["recommendation"] == "new"

        alice.set_user_context(1)
        assert (
            dedup.check_seen(alice, 1, ["https://example.com/jobs/77"])["items"][0][
                "recommendation"
            ]
            == "skip"
        )
    finally:
        alice.close()
        bob.close()


def test_unset_context_sees_no_applications_even_for_the_right_user_id(two_users) -> None:
    # Fail-closed guard for external_applications (mirrors the profiles one).
    # This fails if FORCE RLS or the policy is ever dropped — e.g. when S2
    # FK-recreates this table to add the finding_id FK. Without it, the
    # app-level WHERE user_id filter alone would keep the suite green.
    alice = pg_support.app_connect()
    reader = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        dedup.record_application(alice, 1, url="https://example.com/jobs/77")
        alice.commit()

        # No set_user_context: even asking for user 1, RLS returns nothing.
        assert reader.fetchall("SELECT id FROM external_applications WHERE user_id = 1") == []
        assert (
            dedup.check_seen(reader, 1, ["https://example.com/jobs/77"])["items"][0][
                "recommendation"
            ]
            == "new"
        )
    finally:
        alice.close()
        reader.close()


def test_record_application_is_idempotent_on_postgres(two_users) -> None:
    # Idempotency relies on UNIQUE(user_id, dedup_hash) + RETURNING id —
    # Postgres semantics that differ from SQLite's lastrowid. Prove them live.
    alice = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        first = dedup.record_application(alice, 1, url="https://example.com/jobs/77")
        second = dedup.record_application(
            alice, 1, url="https://example.com/jobs/77/?utm_source=x", notes="again"
        )
        alice.commit()
        assert first["deduped"] is False
        assert second["deduped"] is True
        assert first["external_application_id"] == second["external_application_id"]
        count = alice.fetchone("SELECT COUNT(*) AS n FROM external_applications WHERE user_id = 1")
        assert count["n"] == 1
    finally:
        alice.close()


def test_recompute_merge_respects_unique_constraint_on_postgres(two_users) -> None:
    # The delete-loser-before-update-winner ordering exists precisely so the
    # merge does not trip UNIQUE(user_id, dedup_hash) — a real constraint on PG.
    admin = pg_support.admin_connect()
    try:
        older = admin.insert(
            "INSERT INTO external_applications (user_id, url, channel, dedup_hash)"
            " VALUES (1, ?, 'email', ?)",
            ("https://example.com/jobs/77", "stale-A"),
        )
        admin.insert(
            "INSERT INTO external_applications (user_id, url, channel, dedup_hash)"
            " VALUES (1, ?, 'web', ?)",
            ("https://example.com/jobs/77/?utm_source=x", "stale-B"),
        )
        admin.commit()
    finally:
        admin.close()

    alice = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        report = dedup.recompute_hashes(alice, 1)
        alice.commit()
        assert report["merged"] == 1
        rows = alice.fetchall("SELECT id FROM external_applications WHERE user_id = 1")
        assert len(rows) == 1
        assert rows[0]["id"] == older  # lower id survives
    finally:
        alice.close()
