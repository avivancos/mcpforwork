"""The same UnitOfWork contract holds on SQLite and (live) Postgres.

Runs on SQLite by default and additionally on Postgres under ``-m live`` — the
Sprint 1 demo-gate criterion "one test suite green on BOTH backends".
"""

from mcpforwork.adapters.db.backend import SqlUnitOfWork


def test_insert_and_read_round_trip_on_any_backend(any_uow: SqlUnitOfWork) -> None:
    new_id = any_uow.insert("INSERT INTO users (email) VALUES (?)", ("parity@example.com",))
    any_uow.commit()
    row = any_uow.fetchone("SELECT id, email FROM users WHERE id = ?", (new_id,))
    assert row["id"] == new_id
    assert row["email"] == "parity@example.com"


def test_placeholder_adaptation_holds_on_any_backend(any_uow: SqlUnitOfWork) -> None:
    # `?` placeholders must work regardless of the driver's native style.
    any_uow.insert("INSERT INTO users (email) VALUES (?)", ("q@example.com",))
    any_uow.commit()
    found = any_uow.fetchone("SELECT email FROM users WHERE email = ?", ("q@example.com",))
    missing = any_uow.fetchone("SELECT email FROM users WHERE email = ?", ("nope@example.com",))
    assert found["email"] == "q@example.com"
    assert missing is None


def test_foreign_key_join_round_trips_on_any_backend(any_uow: SqlUnitOfWork) -> None:
    uid = any_uow.insert("INSERT INTO users (email) VALUES (?)", ("fk@example.com",))
    any_uow.insert("INSERT INTO audit_log (user_id, action) VALUES (?, ?)", (uid, "created"))
    any_uow.commit()
    row = any_uow.fetchone(
        "SELECT u.email, a.action FROM users u JOIN audit_log a ON a.user_id = u.id"
    )
    assert row["email"] == "fk@example.com"
    assert row["action"] == "created"
