"""Live-Postgres arm for autopilot L2 (S7.2b): the autopilot_policy table
exists on the real dialect (BOOLEAN/TIMESTAMP vs INTEGER/TEXT), is FORCE-RLS
tenant-isolated, and the L2 authorize/refuse loop works against it.

Requires ``-m live`` and ``TEST_POSTGRES_URL``.
"""

import json

import pytest

import pg_support
from mcpforwork.services import apply as apply_service
from mcpforwork.services import autopilot, hunt, profiles, review

pytestmark = pytest.mark.live

_SAFE = frozenset({"weworkremotely"})


@pytest.fixture
def user():
    if not pg_support.admin_url():
        pytest.skip("TEST_POSTGRES_URL not set")
    admin = pg_support.admin_connect()
    admin.execute(
        "TRUNCATE autopilot_policy, playbook_reports, applications, generated_assets,"
        " explore_findings, external_applications, style_profile, achievements, profiles,"
        " audit_log, users RESTART IDENTITY CASCADE"
    )
    admin.insert("INSERT INTO users (email) VALUES (?)", ("alice@example.com",))
    admin.insert("INSERT INTO users (email) VALUES (?)", ("bob@example.com",))
    admin.commit()
    admin.close()


def _ready_app(uow, uid: int, url: str, score: int = 90) -> int:
    profiles.create_profile(uow, uid, {"full_name": "Ada", "target_titles": ["DE"]})
    hunt.submit_findings(uow, uid, "weworkremotely", [{"url": url, "title": "DE"}])
    # Anchor by URL: list_matches ordering must never pick a prior test finding.
    fid = uow.fetchone("SELECT id FROM explore_findings WHERE url = ? AND user_id = ?", (url, uid))[
        "id"
    ]
    uow.execute("UPDATE explore_findings SET score = ? WHERE id = ?", (score, fid))
    review.approve_match(uow, uid, fid)
    session = apply_service.start_application(uow, uid, fid)
    app_id = session["application_id"]
    for step in session["steps"]:
        apply_service.report_apply_progress(uow, uid, app_id, step["step_id"], "ok")
    apply_service.request_submit(uow, uid, app_id)
    uow.commit()
    return app_id


def test_l2_policy_is_rls_isolated_and_the_loop_works_on_postgres(user) -> None:
    alice = pg_support.app_connect()
    bob = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        assert autopilot.put_policy(alice, 1, min_score=70, max_per_day=2)["ok"] is True
        alice.commit()

        # Cross-tenant: RLS hides alice's policy from bob entirely.
        bob.set_user_context(2)
        assert autopilot.get_policy(bob, 2) is None
        assert autopilot.revoke_policy(bob, 2).get("kind") == "not_found"
        bob.rollback()

        # The full L2 loop on the TIMESTAMP/BOOLEAN dialect.
        app_id = _ready_app(alice, 1, "https://x.com/l2live", score=90)
        result = apply_service.request_submit(alice, 1, app_id, safe_sources=_SAFE)
        alice.commit()
        assert result["decision"] == "submit_authorized"
        row = alice.fetchone("SELECT consent_level FROM applications WHERE id = ?", (app_id,))
        assert row["consent_level"] == 2
        detail = alice.fetchone(
            "SELECT detail FROM audit_log WHERE action = 'submit_authorized' AND user_id = 1"
        )["detail"]
        snapshot = json.loads(detail)["snapshot"]
        assert snapshot["score"] == 90 and snapshot["cap_used"] == 1

        # Revoke mid-batch: the next application awaits the human.
        assert autopilot.revoke_policy(alice, 1)["ok"] is True
        app2 = _ready_app(alice, 1, "https://x.com/l2live2", score=95)
        assert (
            apply_service.request_submit(alice, 1, app2, safe_sources=_SAFE)["decision"]
            == "await_human"
        )
        alice.commit()
    finally:
        alice.close()
        bob.close()
