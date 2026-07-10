"""The Sprint 0 harness enforces its own rules (S0.4 acceptance)."""

import sqlite3

import mcpforwork


def test_package_exposes_a_version() -> None:
    assert mcpforwork.__version__


def test_conn_fixture_is_a_real_file_database_with_enforced_foreign_keys(
    conn: sqlite3.Connection,
) -> None:
    conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
    conn.execute(
        "CREATE TABLE child (id INTEGER PRIMARY KEY,"
        " parent_id INTEGER NOT NULL REFERENCES parent(id))"
    )
    conn.execute("INSERT INTO parent (id) VALUES (1)")
    conn.execute("INSERT INTO child (id, parent_id) VALUES (1, 1)")

    # A real database with PRAGMA foreign_keys=ON must reject an orphan row —
    # this is the fixture behavior every future migration test relies on.
    try:
        conn.execute("INSERT INTO child (id, parent_id) VALUES (2, 999)")
        raise AssertionError("foreign key violation was not enforced")
    except sqlite3.IntegrityError:
        pass

    rows = conn.execute("SELECT COUNT(*) AS n FROM child").fetchone()
    assert rows["n"] == 1
