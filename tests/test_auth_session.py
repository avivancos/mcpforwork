"""Magic-link + session auth core (S6.1a): pure primitives, no HTTP/email.

Time and secret are injected so expiry, single-use, and tamper are all
deterministic. The raw magic-link token is returned to the caller (to deliver)
and NEVER persisted — only its sha256 hash lands in the table.
"""

from datetime import UTC, datetime, timedelta

from mcpforwork.adapters.db.backend import SqlUnitOfWork
from mcpforwork.adapters.db.migrations import SCHEMA_VERSION
from mcpforwork.services import auth_session

_T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
_SECRET = "test-secret-please-rotate"


# --- magic-link tokens -----------------------------------------------------


def test_request_creates_the_user_and_stores_only_the_hash(uow: SqlUnitOfWork) -> None:
    result = auth_session.request_magic_link(uow, "Ada@Example.com", now=_T0)
    uow.commit()
    assert result["raw_token"] and result["user_id"]
    # email normalized to lowercase on the created user
    email = uow.fetchone("SELECT email FROM users WHERE id = ?", (result["user_id"],))["email"]
    assert email == "ada@example.com"
    # ONLY the hash is persisted — the raw token appears nowhere in the row
    row = uow.fetchone(
        "SELECT token_hash FROM magic_link_tokens WHERE user_id = ?", (result["user_id"],)
    )
    assert row["token_hash"] != result["raw_token"]
    assert len(row["token_hash"]) == 64  # sha256 hex digest


def test_request_reuses_an_existing_user_by_email(uow: SqlUnitOfWork) -> None:
    a = auth_session.request_magic_link(uow, "ada@example.com", now=_T0)["user_id"]
    b = auth_session.request_magic_link(uow, "ADA@example.com", now=_T0)["user_id"]
    uow.commit()
    assert a == b  # same email (case-insensitive) -> same account


def test_request_rejects_a_malformed_email(uow: SqlUnitOfWork) -> None:
    assert "error" in auth_session.request_magic_link(uow, "not-an-email", now=_T0)
    assert "error" in auth_session.request_magic_link(uow, "   ", now=_T0)


def test_redeem_returns_the_user_and_is_single_use(uow: SqlUnitOfWork) -> None:
    req = auth_session.request_magic_link(uow, "ada@example.com", now=_T0)
    uow.commit()
    first = auth_session.redeem_magic_link(uow, req["raw_token"], now=_T0 + timedelta(minutes=1))
    uow.commit()
    assert first["user_id"] == req["user_id"]
    # second redemption of the same token is refused
    second = auth_session.redeem_magic_link(uow, req["raw_token"], now=_T0 + timedelta(minutes=2))
    assert "error" in second
    assert "user_id" not in second


def test_redeem_rejects_an_expired_token(uow: SqlUnitOfWork) -> None:
    req = auth_session.request_magic_link(uow, "ada@example.com", now=_T0, ttl_minutes=15)
    uow.commit()
    # one second past expiry
    late = auth_session.redeem_magic_link(
        uow, req["raw_token"], now=_T0 + timedelta(minutes=15, seconds=1)
    )
    assert "error" in late
    # and just before expiry it still works
    req2 = auth_session.request_magic_link(uow, "bob@example.com", now=_T0, ttl_minutes=15)
    uow.commit()
    ok = auth_session.redeem_magic_link(
        uow, req2["raw_token"], now=_T0 + timedelta(minutes=14, seconds=59)
    )
    assert ok["user_id"] == req2["user_id"]


def test_redeem_rejects_unknown_and_tampered_tokens(uow: SqlUnitOfWork) -> None:
    req = auth_session.request_magic_link(uow, "ada@example.com", now=_T0)
    uow.commit()
    assert "error" in auth_session.redeem_magic_link(uow, "not-a-real-token", now=_T0)
    assert "error" in auth_session.redeem_magic_link(uow, req["raw_token"] + "x", now=_T0)


def test_redeem_rejects_a_token_at_the_exact_expiry_instant(uow: SqlUnitOfWork) -> None:
    # Fail-closed: now == expires_at is expired (guards the <=-vs-< off-by-one).
    req = auth_session.request_magic_link(uow, "ada@example.com", now=_T0, ttl_minutes=15)
    uow.commit()
    assert "error" in auth_session.redeem_magic_link(
        uow, req["raw_token"], now=_T0 + timedelta(minutes=15)
    )


def test_redeem_is_single_use_across_separate_connections(uow: SqlUnitOfWork, tmp_path) -> None:
    # The atomic `UPDATE ... WHERE used_at IS NULL` must hold across connections,
    # not just within one — a redeemed token committed by conn A is dead for a
    # FRESH conn B. Real SQLite file, two real UnitOfWorks, zero mocks.
    from mcpforwork.adapters.db import connect

    req = auth_session.request_magic_link(uow, "ada@example.com", now=_T0)
    uow.commit()
    first = auth_session.redeem_magic_link(uow, req["raw_token"], now=_T0 + timedelta(minutes=1))
    uow.commit()
    assert first["user_id"] == req["user_id"]

    other = connect(f"sqlite:///{tmp_path / 'mcpforwork.db'}")
    try:
        again = auth_session.redeem_magic_link(
            other, req["raw_token"], now=_T0 + timedelta(minutes=2)
        )
        assert "error" in again  # already used, seen from a separate connection
    finally:
        other.close()


# --- signed sessions -------------------------------------------------------


def test_session_round_trips_the_user_id() -> None:
    cookie = auth_session.issue_session(42, secret=_SECRET, now=_T0)
    assert auth_session.read_session(cookie, secret=_SECRET, now=_T0 + timedelta(days=1)) == 42


def test_session_rejects_tamper_wrong_secret_and_garbage() -> None:
    cookie = auth_session.issue_session(42, secret=_SECRET, now=_T0)
    assert auth_session.read_session(cookie + "x", secret=_SECRET, now=_T0) is None
    assert auth_session.read_session(cookie, secret="a-different-secret", now=_T0) is None
    assert auth_session.read_session("garbage", secret=_SECRET, now=_T0) is None
    assert auth_session.read_session("", secret=_SECRET, now=_T0) is None


def test_session_expires_past_max_age() -> None:
    # Lifetime is fixed at ISSUE time (embedded exp) — the reader can't widen it.
    cookie = auth_session.issue_session(42, secret=_SECRET, now=_T0, max_age_s=3600)
    assert auth_session.read_session(cookie, secret=_SECRET, now=_T0 + timedelta(minutes=30)) == 42
    assert auth_session.read_session(cookie, secret=_SECRET, now=_T0 + timedelta(hours=2)) is None


def test_session_is_rejected_at_the_exact_expiry_instant() -> None:
    # Fail-closed at the boundary: now == exp must be rejected (guards the
    # >=-vs-> off-by-one the mutant probe exposed).
    cookie = auth_session.issue_session(7, secret=_SECRET, now=_T0, max_age_s=3600)
    assert auth_session.read_session(cookie, secret=_SECRET, now=_T0 + timedelta(seconds=3599)) == 7
    assert (
        auth_session.read_session(cookie, secret=_SECRET, now=_T0 + timedelta(seconds=3600)) is None
    )


def test_read_session_rejects_a_validly_signed_but_wrong_shaped_payload() -> None:
    # Type confusion defense: a future producer that signs a bad shape (string
    # uid, bool uid, non-dict, missing exp) must not authenticate. Uses the SAME
    # real itsdangerous serializer/salt — no mock, just a hostile-but-signed value.
    from itsdangerous import URLSafeSerializer

    s = URLSafeSerializer(_SECRET, salt="mcpforwork.session.v1")
    future = _T0 + timedelta(hours=1)
    exp = int(future.timestamp()) + 3600
    assert (
        auth_session.read_session(s.dumps({"uid": "42", "exp": exp}), secret=_SECRET, now=future)
        is None
    )
    assert (
        auth_session.read_session(s.dumps({"uid": True, "exp": exp}), secret=_SECRET, now=future)
        is None
    )
    assert auth_session.read_session(s.dumps({"uid": 42}), secret=_SECRET, now=future) is None
    assert (
        auth_session.read_session(s.dumps(["not", "a", "dict"]), secret=_SECRET, now=future) is None
    )


# --- migration -------------------------------------------------------------


def test_migration_v8_creates_the_magic_link_table(uow: SqlUnitOfWork) -> None:
    assert SCHEMA_VERSION >= 8
    assert uow.fetchone("SELECT COUNT(*) AS n FROM magic_link_tokens")["n"] == 0
