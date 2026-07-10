"""Dual-backend connection adapter selected by the database URL.

SQLite (default, self-host) and Postgres (psycopg v3, hosted) behind one
`UnitOfWork` surface, so service code never branches on the dialect. The SQLite
path mirrors startup-jobs-radar's proven `backend.connect` (row_factory,
`PRAGMA foreign_keys=ON`, `busy_timeout`); Postgres uses `dict_row`. Fetches
return plain dicts on both backends.

psycopg is imported lazily so SQLite-only self-host installs never load it and
need not install the `postgres` extra.
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

_PSYCOPG_MISSING_MSG = (
    "The database URL points at Postgres but psycopg is not installed. "
    "Install the Postgres extra (`uv add 'mcpforwork[postgres]'` / "
    "`pip install 'mcpforwork[postgres]'`) or use a sqlite:/// URL."
)


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


def _connect_postgres(url: str) -> Any:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:  # pragma: no cover - only without the postgres extra
        raise ImportError(_PSYCOPG_MISSING_MSG) from exc
    return psycopg.connect(url, row_factory=dict_row)


class SqlUnitOfWork:
    """A per-request database handle implementing `ports.db.UnitOfWork`.

    One class serves both dialects; `?` placeholders are adapted to `%s` when
    `is_postgres`.
    """

    def __init__(self, conn: Any, *, is_postgres: bool) -> None:
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

    def insert(self, sql: str, params: Sequence[Any] = ()) -> int:
        # Postgres has no lastrowid — the INSERT must carry RETURNING id.
        if self._is_postgres:
            cur = self.execute(sql + " RETURNING id", params)
            return cur.fetchone()["id"]
        return self.execute(sql, params).lastrowid

    def set_user_context(self, user_id: int) -> None:
        """Bind the tenant for Postgres row-level security; a no-op on SQLite.

        Session-scoped (`is_local=false`), NOT `SET LOCAL`: services commit
        mid-flow and keep querying on the same fresh-per-request connection, so
        a transaction-scoped setting would reset to empty after the first
        commit and make FORCE-RLS fail closed for the rest of the request. The
        function form `set_config` is used because a bare `SET` cannot bind a
        placeholder. On SQLite, isolation is the app-level WHERE user_id filter.
        """
        if not self._is_postgres:
            return
        self._conn.cursor().execute(
            "SELECT set_config('app.current_user_id', %s, false)", (str(user_id),)
        )

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


def connect(url: str | Path, *, run_migrations: bool = True) -> SqlUnitOfWork:
    """Open a connection for `url` and return a `UnitOfWork`.

    Accepts a `sqlite:///…` / `postgres://…` URL or a bare filesystem path.
    Migrations run by default (self-host ergonomics). Pass
    `run_migrations=False` for a connection as the restricted Postgres app
    role, which cannot run DDL — migrations there are an admin/deploy step run
    once by a privileged connection.
    """
    url_str = str(url)
    if _is_postgres_url(url_str):
        conn = _connect_postgres(url_str)
        uow = SqlUnitOfWork(conn, is_postgres=True)
        if run_migrations:
            migrations.migrate_postgres(conn)
        return uow
    conn = _connect_sqlite(url_str)
    if run_migrations:
        migrations.migrate_sqlite(conn)
    return SqlUnitOfWork(conn, is_postgres=False)
