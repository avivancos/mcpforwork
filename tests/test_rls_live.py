"""Live-Postgres row-level-security: tenant isolation, fail-closed, WITH CHECK.

The RLS *mechanism* is proven here on a representative per-user probe table
created for the test, connecting as the restricted ``app`` role so FORCE RLS
applies. Real per-user tables (profiles, external_applications) enable the same
policy in their own migrations (S1.3/S1.4) and re-verify isolation there.

Requires ``-m live`` and ``TEST_POSTGRES_URL``.
"""

import psycopg
import pytest

import pg_support

pytestmark = pytest.mark.live

# The standard per-tenant policy (first, inline use — extracted to a shared
# helper on the second use in S1.3, per the rule of two). NULLIF(...) -> NULL
# when the GUC is unset, so an unset session matches no rows (fail-closed).
_PROBE_STATEMENTS = [
    "CREATE TABLE rls_probe (id BIGSERIAL PRIMARY KEY, user_id BIGINT NOT NULL, val TEXT NOT NULL)",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON rls_probe TO app",
    "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app",
    "ALTER TABLE rls_probe ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE rls_probe FORCE ROW LEVEL SECURITY",
    "CREATE POLICY rls_user_policy ON rls_probe"
    " USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)"
    " WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)",
]


@pytest.fixture
def probe():
    """Admin-owned per-user probe table with the standard RLS policy, seeded
    with one row for tenant 1 and one for tenant 2."""
    if not pg_support.admin_url():
        pytest.skip("TEST_POSTGRES_URL not set")
    admin = pg_support.admin_connect()
    admin.execute("DROP TABLE IF EXISTS rls_probe")
    admin.commit()
    for stmt in _PROBE_STATEMENTS:
        admin.execute(stmt)
    admin.commit()
    # Seed as the superuser, which bypasses RLS.
    admin.insert("INSERT INTO rls_probe (user_id, val) VALUES (?, ?)", (1, "alice"))
    admin.insert("INSERT INTO rls_probe (user_id, val) VALUES (?, ?)", (2, "bob"))
    admin.commit()
    try:
        yield admin
    finally:
        admin.execute("DROP TABLE IF EXISTS rls_probe")
        admin.commit()
        admin.close()


def test_each_tenant_sees_only_its_own_rows(probe) -> None:
    app = pg_support.app_connect()
    try:
        app.set_user_context(1)
        assert {r["val"] for r in app.fetchall("SELECT val FROM rls_probe")} == {"alice"}
        app.set_user_context(2)
        assert {r["val"] for r in app.fetchall("SELECT val FROM rls_probe")} == {"bob"}
    finally:
        app.close()


def test_unset_user_context_sees_no_rows(probe) -> None:
    # Fail-closed: a fresh app connection that never set a tenant sees nothing.
    app = pg_support.app_connect()
    try:
        assert app.fetchall("SELECT val FROM rls_probe") == []
    finally:
        app.close()


def test_tenant_cannot_write_a_row_owned_by_another_tenant(probe) -> None:
    app = pg_support.app_connect()
    try:
        app.set_user_context(1)
        with pytest.raises(psycopg.Error):
            app.execute("INSERT INTO rls_probe (user_id, val) VALUES (2, 'evil')")
            app.commit()
        app.rollback()
        # And tenant 1's own rows are untouched.
        app.set_user_context(1)
        assert {r["val"] for r in app.fetchall("SELECT val FROM rls_probe")} == {"alice"}
    finally:
        app.close()
