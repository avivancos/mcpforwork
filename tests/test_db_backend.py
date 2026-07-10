"""UnitOfWork adapter contract on SQLite — the seam every service depends on."""

import sqlite3
from pathlib import Path

from mcpforwork.adapters.db import connect
from mcpforwork.adapters.db.backend import SqlUnitOfWork


def test_connect_returns_a_sqlite_backed_unit_of_work(tmp_path: Path) -> None:
    uow = connect(f"sqlite:///{tmp_path / 'mcpforwork.db'}")
    try:
        assert uow.is_postgres is False
    finally:
        uow.close()


def test_fetchone_returns_a_dict_keyed_by_column_name(uow: SqlUnitOfWork) -> None:
    new_id = uow.insert("INSERT INTO users (email) VALUES (?)", ("a@example.com",))
    row = uow.fetchone("SELECT id, email FROM users WHERE email = ?", ("a@example.com",))
    assert isinstance(row, dict)
    assert row["email"] == "a@example.com"
    assert row["id"] == new_id


def test_fetchall_returns_a_list_of_dicts(uow: SqlUnitOfWork) -> None:
    uow.insert("INSERT INTO users (email) VALUES (?)", ("b@example.com",))
    uow.insert("INSERT INTO users (email) VALUES (?)", ("c@example.com",))
    rows = uow.fetchall("SELECT email FROM users ORDER BY email")
    assert [r["email"] for r in rows] == ["b@example.com", "c@example.com"]


def test_insert_returns_the_id_of_the_new_row(uow: SqlUnitOfWork) -> None:
    first = uow.insert("INSERT INTO users (email) VALUES (?)", ("d@example.com",))
    second = uow.insert("INSERT INTO users (email) VALUES (?)", ("e@example.com",))
    assert second == first + 1


def test_set_user_context_is_a_noop_on_sqlite(uow: SqlUnitOfWork) -> None:
    # SQLite has no RLS; isolation is app-level WHERE user_id. This must not raise.
    uow.set_user_context(42)


def test_rollback_discards_uncommitted_writes(uow: SqlUnitOfWork) -> None:
    uow.insert("INSERT INTO users (email) VALUES (?)", ("f@example.com",))
    uow.rollback()
    assert uow.fetchone("SELECT id FROM users WHERE email = ?", ("f@example.com",)) is None


def test_uow_wraps_a_real_file_database(uow: SqlUnitOfWork, tmp_path: Path) -> None:
    backing = uow.fetchone("PRAGMA database_list")
    assert isinstance(uow._conn, sqlite3.Connection)
    assert backing["file"] == str(tmp_path / "mcpforwork.db")
