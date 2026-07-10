"""Schema migration runner (SQLite dialect).

Ported from startup-jobs-radar's `db.py` runner pattern: SQLite walks
`PRAGMA user_version` over an inline `MIGRATIONS` dict, applying each pending
version's script in order. Table-recreation migrations (DROP + RENAME of a
parent referenced by FK children) toggle `PRAGMA foreign_keys` off around the
script — the SQLite-standard safe-recreation pattern — because with foreign
keys enforced the DROP would raise, and the PRAGMA is a no-op inside an open
transaction.

The Postgres migration branch lands with the Postgres adapter in S1.2.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# The version the base schema.sql establishes. Each entry in MIGRATIONS bumps
# this; today the base schema is the whole story.
SCHEMA_VERSION = 1

# version -> SQL script. Applied in ascending order for any version above the
# database's current `PRAGMA user_version`. Empty until S1.3 adds the profiles
# tables.
MIGRATIONS: dict[int, str] = {}

# Migrations whose script recreates a table that FK children reference. These
# run with foreign-key enforcement toggled off around the script (see
# `_run_sqlite_migration`).
_FK_RECREATE_MIGRATIONS: frozenset[int] = frozenset()


def migrate(conn: sqlite3.Connection) -> None:
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
