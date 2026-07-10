"""Live-Postgres dialect: migration runner, routing, insert-returning-id.

Requires ``-m live`` and ``TEST_POSTGRES_URL`` (a real local Postgres, e.g. via
Docker). Deselected by default.
"""

import pytest

import pg_support

pytestmark = pytest.mark.live


@pytest.fixture
def admin():
    if not pg_support.admin_url():
        pytest.skip("TEST_POSTGRES_URL not set")
    unit = pg_support.admin_connect()
    unit.execute("TRUNCATE audit_log, users RESTART IDENTITY CASCADE")
    unit.commit()
    try:
        yield unit
    finally:
        unit.close()


def test_postgres_url_routes_to_the_postgres_dialect(admin) -> None:
    assert admin.is_postgres is True


def test_fresh_postgres_database_is_migrated_to_version_one(admin) -> None:
    versions = {r["version"] for r in admin.fetchall("SELECT version FROM schema_migrations")}
    assert 1 in versions
    tables = {
        r["tablename"]
        for r in admin.fetchall("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
    }
    assert {"users", "audit_log", "schema_migrations"} <= tables


def test_re_running_migrations_is_idempotent(admin) -> None:
    # A second connect() re-runs migrate_postgres; ON CONFLICT DO NOTHING must
    # keep exactly one row per version and not error.
    second = pg_support.admin_connect()
    try:
        rows = second.fetchall(
            "SELECT version, count(*) AS n FROM schema_migrations GROUP BY version"
        )
        assert all(r["n"] == 1 for r in rows)
    finally:
        second.close()


def test_insert_returns_id_via_returning_on_postgres(admin) -> None:
    first = admin.insert("INSERT INTO users (email) VALUES (?)", ("pg1@example.com",))
    second = admin.insert("INSERT INTO users (email) VALUES (?)", ("pg2@example.com",))
    admin.commit()
    assert isinstance(first, int)
    assert second > first
