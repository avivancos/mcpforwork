"""Dual-backend connection adapter selected by the database URL.

SQLite (default, self-host) behind the same `UnitOfWork` surface the Postgres
adapter will implement in S1.2, so service code never branches on the dialect.
The SQLite path mirrors startup-jobs-radar's proven `backend.connect`
(row_factory, `PRAGMA foreign_keys=ON`, `busy_timeout`), but fetches return
plain dicts so the row shape is identical on both backends.

The Postgres dialect is deliberately absent until S1.2 — `connect` on a
`postgres://` URL raises `NotImplementedError` rather than shipping an untested
code path.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from mcpforwork.adapters.db import migrations
from mcpforwork.ports.db import Row

_SQLITE_PREFIX = "sqlite:///"
_PG_PREFIXES = ("postgres://", "postgresql://")


def _is_postgres_url(url: str) -> bool:
    return url.startswith(_PG_PREFIXES)


def _sqlite_path(url: str) -> str:
    """The filesystem path from a `sqlite:///…` URL (a bare path is accepted)."""
    if url.startswith(_SQLITE_PREFIX):
        return url[len(_SQLITE_PREFIX) :]
    return url


def _connect_sqlite(url: str) -> sqlite3.Connection:
    path = _sqlite_path(url)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


class SqlUnitOfWork:
    """A per-request database handle implementing `ports.db.UnitOfWork`.

    One class serves both dialects; today only the SQLite path is constructed.
    `?` placeholders are adapted to `%s` when `is_postgres`.
    """

    def __init__(self, conn: sqlite3.Connection, *, is_postgres: bool) -> None:
        self._conn = conn
        self._is_postgres = is_postgres

    @property
    def is_postgres(self) -> bool:
        return self._is_postgres

    def _adapt(self, sql: str) -> str:
        return sql.replace("?", "%s") if self._is_postgres else sql

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        if self._is_postgres:
            cur = self._conn.cursor()
            cur.execute(self._adapt(sql), params)
            return cur
        return self._conn.execute(sql, params)

    def fetchone(self, sql: str, params: Sequence[Any] = ()) -> Row | None:
        row = self.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[Row]:
        return [dict(row) for row in self.execute(sql, params).fetchall()]

    def last_insert_id(self, cur: Any) -> int:
        lastrowid = getattr(cur, "lastrowid", None)
        if lastrowid is not None:
            return lastrowid
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("last_insert_id: INSERT did not RETURNING id")
        try:
            return row["id"]
        except (KeyError, TypeError):
            return row[0]

    def set_user_context(self, user_id: int) -> None:
        # SQLite has no row-level security; isolation is the app-level
        # WHERE user_id filter. The Postgres binding arrives in S1.2.
        return

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


def connect(url: str | Path) -> SqlUnitOfWork:
    """Open a connection for `url`, run migrations, and return a `UnitOfWork`.

    Accepts a `sqlite:///…` URL or a bare filesystem path. A `postgres://` URL
    raises `NotImplementedError` until the Postgres adapter lands in S1.2.
    """
    url_str = str(url)
    if _is_postgres_url(url_str):
        raise NotImplementedError(
            "The Postgres adapter is not implemented yet (arrives in S1.2). "
            "Use a sqlite:/// URL for self-host."
        )
    conn = _connect_sqlite(url_str)
    migrations.migrate(conn)
    return SqlUnitOfWork(conn, is_postgres=False)
