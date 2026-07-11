"""Live-Postgres: generated_assets tenant isolation + coverage works on PG.

Requires ``-m live`` and ``TEST_POSTGRES_URL``.
"""

import pytest

import pg_support
from mcpforwork.services import assets, coverage, hunt, profiles

pytestmark = pytest.mark.live


@pytest.fixture
def two_users():
    if not pg_support.admin_url():
        pytest.skip("TEST_POSTGRES_URL not set")
    admin = pg_support.admin_connect()
    admin.execute(
        "TRUNCATE generated_assets, explore_findings, external_applications, style_profile,"
        " achievements, profiles, audit_log, users RESTART IDENTITY CASCADE"
    )
    admin.insert("INSERT INTO users (email) VALUES (?)", ("alice@example.com",))
    admin.insert("INSERT INTO users (email) VALUES (?)", ("bob@example.com",))
    admin.commit()
    try:
        yield
    finally:
        admin.close()


def _seed_asset(conn, uid: int) -> tuple[int, int]:
    profiles.create_profile(conn, uid, {"target_titles": ["Data Engineer"], "cv_text": "Python."})
    hunt.submit_findings(
        conn,
        uid,
        "weworkremotely",
        [{"url": "https://x.com/1", "title": "Data Engineer", "description": "Python and Spark."}],
    )
    fid = hunt.list_matches(conn, uid, min_score=0)[0]["id"]
    aid = assets.submit_asset(conn, uid, fid, "cv", "Python work.")["asset_id"]
    conn.commit()
    return fid, aid


def test_assets_are_tenant_isolated_and_fail_closed(two_users) -> None:
    alice = pg_support.app_connect()
    bob = pg_support.app_connect()
    reader = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        fid, _ = _seed_asset(alice, 1)

        bob.set_user_context(2)
        assert assets.get_assets(bob, 2, fid) == []  # cross-tenant: nothing

        # Fail-closed: no context, even asking for user 1.
        assert reader.fetchall("SELECT id FROM generated_assets WHERE user_id = 1") == []
    finally:
        alice.close()
        bob.close()
        reader.close()


def test_coverage_check_runs_on_postgres(two_users) -> None:
    # Regression for the S3 gate P1: PG datetime rows crashed _facts_text.
    alice = pg_support.app_connect()
    try:
        alice.set_user_context(1)
        fid, aid = _seed_asset(alice, 1)
        result = coverage.ats_coverage_check(alice, 1, fid, aid)
        assert "spark" in result["genuine_gaps"]
        assert "python" in result["covered"]
    finally:
        alice.close()
