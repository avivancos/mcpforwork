"""UnitOfWork adapter contract — the seam every service depends on (S1.1)."""

import sqlite3
from pathlib import Path

import pytest

from mcpforwork.adapters.db import connect
from mcpforwork.adapters.db.backend import SqlUnitOfWork


def _sqlite_uow(tmp_path: Path) -> SqlUnitOfWork:
    return connect(f"sqlite:///{tmp_path / 'mcpforwork.db'}")


def test_connect_returns_a_sqlite_backed_unit_of_work(tmp_path: Path) -> None:
    uow = _sqlite_uow(tmp_path)
    try:
        assert uow.is_postgres is False
    finally:
        uow.close()


def test_fetchone_returns_a_dict_keyed_by_column_name(uow: SqlUnitOfWork) -> None:
    cur = uow.execute("INSERT INTO users (email) VALUES (?)", ("a@example.com",))
    row = uow.fetchone("SELECT id, email FROM users WHERE email = ?", ("a@example.com",))
    assert isinstance(row, dict)
    assert row["email"] == "a@example.com"
    assert row["id"] == uow.last_insert_id(cur)


def test_fetchall_returns_a_list_of_dicts(uow: SqlUnitOfWork) -> None:
    uow.execute("INSERT INTO users (email) VALUES (?)", ("b@example.com",))
    uow.execute("INSERT INTO users (email) VALUES (?)", ("c@example.com",))
    rows = uow.fetchall("SELECT email FROM users ORDER BY email")
    assert [r["email"] for r in rows] == ["b@example.com", "c@example.com"]


def test_last_insert_id_is_the_id_of_the_row_just_inserted(uow: SqlUnitOfWork) -> None:
    cur1 = uow.execute("INSERT INTO users (email) VALUES (?)", ("d@example.com",))
    cur2 = uow.execute("INSERT INTO users (email) VALUES (?)", ("e@example.com",))
    assert uow.last_insert_id(cur2) == uow.last_insert_id(cur1) + 1


def test_set_user_context_is_a_noop_on_sqlite(uow: SqlUnitOfWork) -> None:
    # SQLite has no RLS; isolation is app-level WHERE user_id. This must not raise.
    uow.set_user_context(42)


def test_rollback_discards_uncommitted_writes(uow: SqlUnitOfWork) -> None:
    uow.execute("INSERT INTO users (email) VALUES (?)", ("f@example.com",))
    uow.rollback()
    assert uow.fetchone("SELECT id FROM users WHERE email = ?", ("f@example.com",)) is None


def test_missing_postgres_driver_surfaces_a_clear_error(tmp_path: Path) -> None:
    # S1.1 ships SQLite only; the Postgres dialect (and its real connect) lands in S1.2.
    with pytest.raises(NotImplementedError):
        connect("postgres://localhost/whatever")


def test_uow_wraps_a_real_file_database(uow: SqlUnitOfWork, tmp_path: Path) -> None:
    backing = uow.fetchone("PRAGMA database_list")
    assert isinstance(uow._conn, sqlite3.Connection)
    assert backing["file"] == str(tmp_path / "mcpforwork.db")
