"""Database adapter — dialect connect + migration runner.

`connect(url)` returns a `ports.db.UnitOfWork`. SQLite is the self-host
default; the Postgres dialect (and row-level security) lands in S1.2. The
SQLite/Postgres split IS the open-core split: every feature must work on the
SQLite adapter with no account.
"""

from mcpforwork.adapters.db.backend import SqlUnitOfWork, connect

__all__ = ["SqlUnitOfWork", "connect"]
