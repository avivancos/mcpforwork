"""Live-Postgres: applications + playbook_reports tenant isolation (S4 gate fix).

Requires ``-m live`` and ``TEST_POSTGRES_URL``.
"""

import pytest

import pg_support
from mcpforwork.services import apply as apply_service
from mcpforwork.services import hunt, playbooks, profiles, review

pytestmark = pytest.mark.live


@pytest.fixture
def two_users():
    if not pg_support.admin_url():
        pytest.skip("TEST_POSTGRES_URL not set")
    admin = pg_support.admin_connect()
    admin.execute(
        "TRUNCATE playbook_reports, applications, generated_assets, explore_findings,"
        " external_applications, style_profile, achievements, profiles, audit_log, users"
        " RESTART IDENTITY CASCADE"
    )
    admin.insert("INSERT INTO users (email) VALUES (?)", ("alice@example.com",))
    admin.insert("INSERT INTO users (email) VALUES (?)", ("bob@example.com",))
    admin.commit()
    try:
        yield
    finally:
        admin.close()


def test_applications_and_reports_are_tenant_isolated_and_fail_closed(two_users) -> None:
    alice = pg_support.app_connect()
    bob = pg_support.app_connect()
    reader = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        profiles.create_profile(alice, 1, {"full_name": "Ada", "target_titles": ["DE"]})
        hunt.submit_findings(
            alice, 1, "weworkremotely", [{"url": "https://x.com/1", "title": "DE"}]
        )
        fid = hunt.list_matches(alice, 1, min_score=0)[0]["id"]
        review.approve_match(alice, 1, fid)
        app_id = apply_service.start_application(alice, 1, fid)["application_id"]
        playbooks.report_playbook_result(alice, 1, "reed", "drift", {"x": 1})
        alice.commit()

        # Cross-tenant: bob sees nothing through the services or raw reads.
        bob.set_user_context(2)
        assert "error" in apply_service.report_apply_progress(bob, 2, app_id, 1, "ok")
        assert bob.fetchall("SELECT id FROM applications") == []
        assert bob.fetchall("SELECT id FROM playbook_reports") == []

        # Fail-closed: no context, even asking for user 1 explicitly.
        assert reader.fetchall("SELECT id FROM applications WHERE user_id = 1") == []
        assert reader.fetchall("SELECT id FROM playbook_reports WHERE user_id = 1") == []
    finally:
        alice.close()
        bob.close()
        reader.close()
