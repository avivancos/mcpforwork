"""Live-Postgres: explore_findings enforces tenant isolation through the hunt
service, as the restricted app role.

Requires ``-m live`` and ``TEST_POSTGRES_URL``.
"""

import pytest

import pg_support
from mcpforwork.services import hunt, profiles

pytestmark = pytest.mark.live


@pytest.fixture
def two_users():
    if not pg_support.admin_url():
        pytest.skip("TEST_POSTGRES_URL not set")
    admin = pg_support.admin_connect()
    admin.execute(
        "TRUNCATE explore_findings, external_applications, style_profile, achievements,"
        " profiles, audit_log, users RESTART IDENTITY CASCADE"
    )
    admin.insert("INSERT INTO users (email) VALUES (?)", ("alice@example.com",))
    admin.insert("INSERT INTO users (email) VALUES (?)", ("bob@example.com",))
    admin.commit()
    try:
        yield
    finally:
        admin.close()


def test_findings_scouted_by_one_tenant_are_invisible_to_another(two_users) -> None:
    alice = pg_support.app_connect()
    bob = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        profiles.create_profile(alice, 1, {"target_titles": ["Data Engineer"]})
        hunt.submit_findings(
            alice, 1, "weworkremotely", [{"url": "https://x.com/1", "title": "Data Engineer"}]
        )
        alice.commit()

        bob.set_user_context(2)
        assert hunt.list_matches(bob, 2, min_score=0) == []

        alice.set_user_context(1)
        assert len(hunt.list_matches(alice, 1, min_score=0)) == 1
    finally:
        alice.close()
        bob.close()


def test_unset_context_reads_no_findings_even_for_the_right_user_id(two_users) -> None:
    alice = pg_support.app_connect()
    reader = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        profiles.create_profile(alice, 1, {"target_titles": ["Data Engineer"]})
        hunt.submit_findings(
            alice, 1, "weworkremotely", [{"url": "https://x.com/1", "title": "Data Engineer"}]
        )
        alice.commit()

        # No set_user_context: RLS fails closed even asking for user 1.
        assert hunt.list_matches(reader, 1, min_score=0) == []
    finally:
        alice.close()
        reader.close()
