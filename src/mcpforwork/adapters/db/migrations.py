"""Schema migration runner (SQLite + Postgres dialects).

Ported from startup-jobs-radar's `db.py` runner pattern.

SQLite walks `PRAGMA user_version` over an inline `MIGRATIONS` dict, applying
each pending version's script in order. Table-recreation migrations (DROP +
RENAME of a parent referenced by FK children) toggle `PRAGMA foreign_keys` off
around the script — the SQLite-standard safe-recreation pattern — because with
foreign keys enforced the DROP would raise, and the PRAGMA is a no-op inside an
open transaction.

Postgres reads ordered `.sql` files from `pg/`, tracks applied versions in a
`schema_migrations` table, and splits each file into statements with a
dollar-quote-aware parser (psycopg has no `executescript`, and a naive
`split(';')` would break the `DO $$ … $$` block that provisions the app role).

The SQLite and Postgres representations of a migration are authored separately
and kept parallel by hand; the parity tests catch behavioral divergence.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"
_PG_DIR = Path(__file__).parent / "pg"

# The version the base schema establishes. Each entry in MIGRATIONS bumps this.
SCHEMA_VERSION = 1

# version -> SQLite SQL script, applied in ascending order above the database's
# current `PRAGMA user_version`. Empty until S1.3 adds the profiles tables.
MIGRATIONS: dict[int, str] = {}

# Migrations whose script recreates a table that FK children reference; these
# run with foreign-key enforcement toggled off around the script.
_FK_RECREATE_MIGRATIONS: frozenset[int] = frozenset()

# Postgres migration file -> version registered in schema_migrations. The file
# ordinal is the version here (unlike the donor's legacy offset).
_PG_MIGRATION_VERSIONS: dict[str, int] = {
    "001_initial.sql": 1,
}


# --------------------------------------------------------------------------- #
# SQLite
# --------------------------------------------------------------------------- #
def migrate_sqlite(conn: sqlite3.Connection) -> None:
    """Bring `conn` up to `SCHEMA_VERSION` (SQLite)."""
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        conn.executescript(_SCHEMA_PATH.read_text())
        version = 1
    for target in sorted(MIGRATIONS):
        if version < target:
            _run_sqlite_migration(
                conn, MIGRATIONS[target], fk_recreate=target in _FK_RECREATE_MIGRATIONS
            )
            version = target
    conn.execute(f"PRAGMA user_version = {version}")
    conn.commit()


def _run_sqlite_migration(conn: sqlite3.Connection, sql: str, *, fk_recreate: bool) -> None:
    """Apply one migration script. When `fk_recreate`, disable foreign-key
    enforcement at the connection level around the script and restore it after,
    so a parent table referenced by children can be dropped and rebuilt."""
    if not fk_recreate:
        conn.executescript(sql)
        return
    # PRAGMA foreign_keys only takes effect outside a transaction, so commit any
    # implicit open transaction first, then toggle around the script.
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


# --------------------------------------------------------------------------- #
# Postgres
# --------------------------------------------------------------------------- #
def migrate_postgres(conn: Any) -> None:
    """Apply Postgres migration files in order, skipping already-applied
    versions. Each file registers its own version with `ON CONFLICT DO NOTHING`,
    so re-running is idempotent. The 001 file creates `schema_migrations`
    before any later check reads it."""
    cur = conn.cursor()
    files = sorted(
        p for p in _PG_DIR.glob("[0-9][0-9][0-9]_*.sql") if p.name in _PG_MIGRATION_VERSIONS
    )
    applied = _applied_pg_versions(conn)
    for path in files:
        version = _PG_MIGRATION_VERSIONS[path.name]
        if version in applied:
            continue
        for stmt in _pg_statements(path.read_text()):
            cur.execute(stmt)
        conn.commit()
        applied.add(version)


def _applied_pg_versions(conn: Any) -> set[int]:
    """Versions already in schema_migrations (empty if the table is absent)."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT version FROM schema_migrations")
        rows = cur.fetchall()
    except Exception:
        conn.rollback()  # the failed statement poisoned the transaction
        return set()
    return {r["version"] for r in rows}


def _pg_statements(sql: str) -> list[str]:
    """Split a SQL script into statements for psycopg (no `executescript`).

    Splits on `;` but respects dollar-quoted blocks (`$$ … $$` or `$tag$ … $tag$`,
    e.g. the `DO $$ BEGIN … END $$;` that provisions the app role): `;` inside
    such a block does not end the statement. Line comments (`-- …`) are copied
    verbatim so a `$$` or `;` mentioned in a comment is not interpreted.
    """
    statements: list[str] = []
    buf: list[str] = []
    dollar_tag: str | None = None
    i = 0
    n = len(sql)
    while i < n:
        if dollar_tag is None:
            if sql.startswith("--", i):
                eol = sql.find("\n", i)
                if eol == -1:
                    buf.append(sql[i:])
                    i = n
                else:
                    buf.append(sql[i : eol + 1])
                    i = eol + 1
                continue
            if sql[i] == "$":
                tag = _dollar_tag_at(sql, i)
                if tag is not None:
                    dollar_tag = tag
                    buf.append(tag)
                    i += len(tag)
                    continue
            if sql[i] == ";":
                stmt = "".join(buf).strip()
                if stmt:
                    statements.append(stmt)
                buf = []
                i += 1
                continue
            buf.append(sql[i])
            i += 1
        else:
            if sql.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
                continue
            buf.append(sql[i])
            i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _dollar_tag_at(sql: str, i: int) -> str | None:
    """If a dollar-quote tag (`$$` or `$name$`) opens at `sql[i]`, return it."""
    if sql[i] != "$":
        return None
    j = sql.find("$", i + 1)
    if j == -1:
        return None
    inner = sql[i + 1 : j]
    if inner == "" or inner.isidentifier():
        return sql[i : j + 1]
    return None
