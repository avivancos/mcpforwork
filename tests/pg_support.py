"""Live-Postgres test support: URLs and connections for the admin and app roles.

Set ``TEST_POSTGRES_URL`` to a superuser URL (used to run migrations and set up
tables). The non-superuser ``app`` role — created by the base migration — is
what per-request connections authenticate as, so FORCE row-level security
applies to it. Tests connect as ``app`` (with migrations skipped, since the
restricted role cannot run DDL) to prove tenant isolation.
"""

from __future__ import annotations

import os
from urllib.parse import urlsplit, urlunsplit

from mcpforwork.adapters.db import SqlUnitOfWork, connect

APP_ROLE = "app"
APP_PASSWORD = "app_secret"  # dev/test default; production overrides via ALTER ROLE


def admin_url() -> str | None:
    return os.environ.get("TEST_POSTGRES_URL")


def app_url(admin: str | None = None) -> str:
    parts = urlsplit(admin or admin_url())
    netloc = f"{APP_ROLE}:{APP_PASSWORD}@{parts.hostname}:{parts.port or 5432}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def admin_connect() -> SqlUnitOfWork:
    """Connect as the migrating superuser (runs migrations)."""
    return connect(admin_url())


def app_connect() -> SqlUnitOfWork:
    """Connect as the restricted app role (no migrations; subject to RLS)."""
    return connect(app_url(), run_migrations=False)
