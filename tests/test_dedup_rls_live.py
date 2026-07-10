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
