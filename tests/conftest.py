"""Shared fixtures — zero-mocks harness (AGENTS.md §Testing contract).

Conventions established here:
- Database tests run against a REAL SQLite file at tmp_path (never :memory:,
  never a mock) so file-locking, PRAGMA, and transaction behavior match
  production self-host installs.
- Postgres arms are added per-test via
  @pytest.fixture(params=["sqlite", pytest.param("postgres", marks=pytest.mark.live)])
  once the Postgres adapter lands (S1.2); `live` is excluded by default.
- HTTP dependencies use pytest-httpserver with recorded fixtures — never
  invented provider behavior.
"""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Real SQLite connection on a real file, foreign keys enforced.

    Low-level and NOT migrated — migration tests need a virgin database. Service
    and dedup tests should take the migrated ``uow`` fixture instead.
    """
    connection = sqlite3.connect(tmp_path / "mcpforwork.db")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def uow(tmp_path: Path) -> Iterator["object"]:
    """A migrated UnitOfWork on a real SQLite file — the seam services take.

    S1.2 parametrizes this over sqlite and (live) postgres; today it is
    SQLite-only. Imported lazily so the fixture module has no import-time
    dependency on the adapter before S1.1's code exists.
    """
    from mcpforwork.adapters.db import connect

    unit = connect(f"sqlite:///{tmp_path / 'mcpforwork.db'}")
    try:
        yield unit
    finally:
        unit.close()
