"""Live-Postgres (S6.1a): magic_link_tokens is a PRE-AUTH table.

The whole point is that login happens BEFORE a tenant context exists, so the
`app` role must be able to request and redeem a magic link with NO
set_user_context — magic_link_tokens is deliberately NOT RLS-forced. This proves
the grant + no-RLS decision on the real backend.

Requires ``-m live`` and ``TEST_POSTGRES_URL``.
"""

from datetime import UTC, datetime, timedelta

import pytest

import pg_support
from mcpforwork.services import auth_session

pytestmark = pytest.mark.live

_T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def app_conn():
    if not pg_support.admin_url():
        pytest.skip("TEST_POSTGRES_URL not set")
    admin = pg_support.admin_connect()
    admin.execute("TRUNCATE magic_link_tokens, sessions, users RESTART IDENTITY CASCADE")
    admin.commit()
    admin.close()
    conn = pg_support.app_connect()  # the non-superuser RLS-bound role
    try:
        yield conn
    finally:
        conn.close()


def test_app_role_requests_and_redeems_without_a_user_context(app_conn) -> None:
    # NO set_user_context is called — a magic link is issued/redeemed pre-auth.
    req = auth_session.request_magic_link(app_conn, "ada@example.com", now=_T0)
    app_conn.commit()
    assert req["user_id"]

    redeemed = auth_session.redeem_magic_link(
        app_conn, req["raw_token"], now=_T0 + timedelta(minutes=1)
    )
    app_conn.commit()
    assert redeemed["user_id"] == req["user_id"]

    # single-use holds on Postgres too
    again = auth_session.redeem_magic_link(
        app_conn, req["raw_token"], now=_T0 + timedelta(minutes=2)
    )
    assert "error" in again


def test_expiry_is_enforced_on_postgres(app_conn) -> None:
    req = auth_session.request_magic_link(app_conn, "bob@example.com", now=_T0, ttl_minutes=15)
    app_conn.commit()
    late = auth_session.redeem_magic_link(
        app_conn, req["raw_token"], now=_T0 + timedelta(minutes=16)
    )
    assert "error" in late


# --- sessions table (RLS-forced, unlike the pre-auth magic_link_tokens) -----


def test_sessions_insert_requires_the_user_context(app_conn) -> None:
    # sessions is RLS-forced: with NO tenant context the WITH CHECK rejects the
    # insert — the redeem route sets the context right after token redemption.
    import psycopg.errors

    app_conn.execute("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
    app_conn.commit()
    try:
        auth_session.issue_session(app_conn, 1, secret="s", now=_T0)
        app_conn.commit()
        raise AssertionError("insert without user context must be rejected")
    except psycopg.errors.Error:
        app_conn.rollback()
    app_conn.set_user_context(1)
    cookie = auth_session.issue_session(app_conn, 1, secret="s", now=_T0)
    app_conn.commit()
    assert cookie


def test_sessions_are_tenant_scoped_under_rls(app_conn) -> None:
    app_conn.execute("INSERT INTO users (id, email) VALUES (1, 'a@example.com')")
    app_conn.execute("INSERT INTO users (id, email) VALUES (2, 'b@example.com')")
    app_conn.commit()
    app_conn.set_user_context(2)
    bob_sid = auth_session.read_session(
        auth_session.issue_session(app_conn, 2, secret="s", now=_T0), secret="s", now=_T0
    )["sid"]
    app_conn.commit()

    # user 1's context cannot see or revoke user 2's session row
    app_conn.set_user_context(1)
    assert auth_session.get_session(app_conn, bob_sid) is None
    assert auth_session.revoke_session(app_conn, 1, bob_sid, now=_T0) is False
    app_conn.set_user_context(2)
    assert auth_session.get_session(app_conn, bob_sid) is not None
