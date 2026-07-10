"""Live-Postgres: the real profile tables enforce tenant isolation through the
service, as the restricted app role. Proves the 002_profiles.sql RLS policy on
the actual tables (not just the S1.2 probe table).

Requires ``-m live`` and ``TEST_POSTGRES_URL``.
"""

import pytest

import pg_support
from mcpforwork.services import profiles

pytestmark = pytest.mark.live


@pytest.fixture
def two_users():
    """Admin-migrated schema with users 1 and 2 seeded; per-user tables truncated."""
    if not pg_support.admin_url():
        pytest.skip("TEST_POSTGRES_URL not set")
    admin = pg_support.admin_connect()
    admin.execute(
        "TRUNCATE style_profile, achievements, profiles, audit_log, users RESTART IDENTITY CASCADE"
    )
    admin.insert("INSERT INTO users (email) VALUES (?)", ("alice@example.com",))
    admin.insert("INSERT INTO users (email) VALUES (?)", ("bob@example.com",))
    admin.commit()
    try:
        yield
    finally:
        admin.close()


def test_profile_created_by_one_tenant_is_invisible_to_another(two_users) -> None:
    alice = pg_support.app_connect()
    bob = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        profiles.create_profile(alice, 1, {"full_name": "Alice"})
        alice.commit()

        bob.set_user_context(2)
        assert profiles.list_profiles(bob, 2) == []

        alice.set_user_context(1)
        assert profiles.get_profile(alice, 1)["full_name"] == "Alice"
    finally:
        alice.close()
        bob.close()


def test_unset_context_reads_no_profiles_even_for_the_right_user_id(two_users) -> None:
    alice = pg_support.app_connect()
    reader = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        profiles.create_profile(alice, 1, {"full_name": "Alice"})
        alice.commit()

        # No set_user_context: RLS fails closed even when asked for user 1.
        assert profiles.list_profiles(reader, 1) == []
    finally:
        alice.close()
        reader.close()
