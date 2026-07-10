"""The database port — the seam services depend on.

A ``UnitOfWork`` is a per-request database handle. Services take ``(uow,
user_id, ...)`` and the caller owns the transaction (commit/rollback), so the
consent/caps/dedup gates in services compose into one atomic unit the
entrypoint controls. Rows are plain ``dict`` keyed by column name on every
backend, so service code never branches on the dialect.

This is one of the named ports, so a single implementation is sanctioned by
the anti-over-engineering charter (AGENTS.md §3).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

Row = dict[str, Any]


@runtime_checkable
class UnitOfWork(Protocol):
    """A dialect-neutral, per-request database handle."""

    @property
    def is_postgres(self) -> bool: ...

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Any:
        """Run a statement; return the driver cursor. ``?`` placeholders are
        adapted to the backend."""

    def fetchone(self, sql: str, params: Sequence[Any] = ()) -> Row | None: ...

    def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[Row]: ...

    def insert(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Run an INSERT and return the new row's ``id``, uniform across
        backends (SQLite ``lastrowid``; Postgres ``RETURNING id``). The table's
        surrogate key must be named ``id``."""

    def set_user_context(self, user_id: int) -> None:
        """Bind the tenant for Postgres row-level security; a no-op on SQLite."""

    def commit(self) -> None: ...

    def rollback(self) -> None: ...

    def close(self) -> None: ...
