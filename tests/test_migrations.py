"""Migration runner — fresh migrate, idempotence, FK-safe recreation (S1.1)."""

import sqlite3
from pathlib import Path

from mcpforwork.adapters.db import connect
from mcpforwork.adapters.db.migrations import SCHEMA_VERSION, _run_sqlite_migration


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {r["name"] for r in rows}


def test_fresh_database_migrates_to_the_current_version(tmp_path: Path) -> None:
    uow = connect(f"sqlite:///{tmp_path / 'fresh.db'}")
    try:
        version = uow.fetchone("PRAGMA user_version")["user_version"]
        assert version == SCHEMA_VERSION
        assert {"users", "audit_log"} <= _table_names(uow._conn)
    finally:
        uow.close()


def test_migrating_an_already_current_database_is_a_noop(tmp_path: Path) -> None:
    path = f"sqlite:///{tmp_path / 'again.db'}"
    connect(path).close()  # first run creates the schema
    uow = connect(path)  # second run must not error or re-create tables
    try:
        assert uow.fetchone("PRAGMA user_version")["user_version"] == SCHEMA_VERSION
    finally:
        uow.close()


def test_fk_recreate_migration_preserves_child_references(conn: sqlite3.Connection) -> None:
    # The pattern S1.3/S1.4 table-recreation migrations depend on: with
    # PRAGMA foreign_keys=ON, dropping a parent referenced by children raises;
    # the FK-recreate helper toggles the PRAGMA off around the script and back on.
    conn.executescript(
        """
        CREATE TABLE parent (id INTEGER PRIMARY KEY, label TEXT);
        CREATE TABLE child (id INTEGER PRIMARY KEY,
                            parent_id INTEGER NOT NULL REFERENCES parent(id));
        INSERT INTO parent (id, label) VALUES (1, 'old');
        INSERT INTO child (id, parent_id) VALUES (1, 1);
        """
    )
    conn.commit()

    recreate = """
        CREATE TABLE parent_new (id INTEGER PRIMARY KEY, label TEXT, extra TEXT);
        INSERT INTO parent_new (id, label) SELECT id, label FROM parent;
        DROP TABLE parent;
        ALTER TABLE parent_new RENAME TO parent;
    """
    _run_sqlite_migration(conn, recreate, fk_recreate=True)

    # The child's reference survived the parent's recreation...
    child = conn.execute("SELECT parent_id FROM child WHERE id = 1").fetchone()
    assert child["parent_id"] == 1
    assert conn.execute("SELECT extra FROM parent WHERE id = 1").fetchone() is not None

    # ...and foreign keys are enforced again afterwards.
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    try:
        conn.execute("INSERT INTO child (id, parent_id) VALUES (2, 999)")
        raise AssertionError("foreign keys were not restored after the recreate")
    except sqlite3.IntegrityError:
        pass
