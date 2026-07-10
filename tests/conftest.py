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
    """Real SQLite connection on a real file, foreign keys enforced."""
    connection = sqlite3.connect(tmp_path / "mcpforwork.db", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    try:
        yield connection
    finally:
        connection.close()
