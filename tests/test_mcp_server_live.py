"""Live-Postgres: the MCP tools serialize PG-native TIMESTAMP columns.

On Postgres, created_at/first_seen/last_seen deserialize to datetime; the tools
must still return valid JSON (the SQLite all-TEXT path hid this). Drives the
tools against the live DB as the admin role — this checks serialization, not
isolation.

Requires ``-m live`` and ``TEST_POSTGRES_URL``.
"""

import json

import pytest

import pg_support

pytestmark = pytest.mark.live


@pytest.fixture
def pg_entrypoint_env(monkeypatch):
    if not pg_support.admin_url():
        pytest.skip("TEST_POSTGRES_URL not set")
    admin = pg_support.admin_connect()
    admin.execute(
        "TRUNCATE explore_findings, external_applications, style_profile, achievements,"
        " profiles, audit_log, users RESTART IDENTITY CASCADE"
    )
    admin.commit()
    admin.close()
    monkeypatch.setenv("MCPFORWORK_DB_URL", pg_support.admin_url())
    monkeypatch.setenv("MCPFORWORK_USER_ID", "1")


def test_profile_and_match_tools_serialize_postgres_timestamps(pg_entrypoint_env) -> None:
    from mcpforwork.entrypoints.mcp import server

    created = json.loads(server.update_profile({"target_titles": ["Data Engineer"]}))
    assert created["ok"] is True
    assert "T" in created["profile"]["created_at"]  # ISO timestamp, not a crash

    plan = json.loads(server.hunt_plan())
    slug = plan["sources"][0]["slug"]
    server.submit_findings(slug, [{"url": "https://x.com/1", "title": "Data Engineer"}])
    matches = json.loads(server.list_matches(0))["matches"]
    assert matches[0]["title"] == "Data Engineer"
    assert "T" in matches[0]["first_seen"]
