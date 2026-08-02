"""Live-Postgres arm for autopilot L1 (S7.2a): the approval columns exist and
the full L1 loop works on the real dialect (TIMESTAMP vs TEXT), with tenant
isolation inherited from the applications RLS policy.

Requires ``-m live`` and ``TEST_POSTGRES_URL``.
"""

import pytest

import pg_support
from mcpforwork.services import apply as apply_service
from mcpforwork.services import autopilot, hunt, profiles, review

pytestmark = pytest.mark.live


@pytest.fixture
def user():
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
    admin.close()


def test_l1_loop_works_on_postgres_and_stays_tenant_isolated(user) -> None:
    alice = pg_support.app_connect()
    bob = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        profiles.create_profile(alice, 1, {"full_name": "Ada", "target_titles": ["DE"]})
        hunt.submit_findings(
            alice, 1, "weworkremotely", [{"url": "https://x.com/l1", "title": "DE"}]
        )
        fid = hunt.list_matches(alice, 1, min_score=0)[0]["id"]
        review.approve_match(alice, 1, fid)
        session = apply_service.start_application(alice, 1, fid)
        app_id = session["application_id"]
        for step in session["steps"]:
            apply_service.report_apply_progress(alice, 1, app_id, step["step_id"], "ok")
        apply_service.request_submit(alice, 1, app_id)
        alice.commit()

        # Cross-tenant: bob cannot approve alice's application (RLS + scoping).
        bob.set_user_context(2)
        assert autopilot.approve_submit(bob, 2, app_id).get("kind") == "not_found"
        bob.rollback()

        # Alice approves (the API's service call), the agent re-enters and is
        # authorized exactly once on the TIMESTAMP dialect too.
        assert autopilot.approve_submit(alice, 1, app_id, via="dashboard")["ok"] is True
        first = apply_service.request_submit(alice, 1, app_id)
        alice.commit()
        assert first["decision"] == "submit_authorized"
        row = alice.fetchone(
            "SELECT consent_level, submit_approved_via FROM applications WHERE id = ?", (app_id,)
        )
        assert row["consent_level"] == 1
        assert row["submit_approved_via"] == "dashboard"
        assert (
            alice.fetchone(
                "SELECT COUNT(*) AS n FROM audit_log"
                " WHERE action = 'submit_authorized' AND user_id = 1"
            )["n"]
            == 1
        )
    finally:
        alice.close()
        bob.close()
