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

# The version the base schema establishes plus each migration. Bumped as
# MIGRATIONS grows.
SCHEMA_VERSION = 11

# version -> SQLite SQL script, applied in ascending order above the database's
# current `PRAGMA user_version`.
_PROFILES_SQLITE = """
CREATE TABLE profiles (
  id                   INTEGER PRIMARY KEY,
  user_id              INTEGER NOT NULL REFERENCES users(id),
  label                TEXT NOT NULL DEFAULT 'default',
  is_active            INTEGER NOT NULL DEFAULT 1,
  full_name            TEXT,
  contact_email        TEXT,
  country              TEXT,
  city                 TEXT,
  work_auth_countries  TEXT,   -- JSON list
  needs_sponsorship    INTEGER,
  target_titles        TEXT,   -- JSON list (1-5)
  sectors              TEXT,   -- JSON list
  seniority            TEXT,
  employment_types     TEXT,   -- JSON list
  work_modes           TEXT,   -- JSON list
  relocation           INTEGER,
  min_salary_amount    INTEGER,
  min_salary_currency  TEXT,
  min_salary_period    TEXT,
  languages            TEXT,   -- JSON list
  cv_text              TEXT,
  links                TEXT,   -- JSON dict
  availability_date    TEXT,
  notice_period        TEXT,
  deal_breakers        TEXT,   -- JSON
  career_narrative     TEXT,
  salary_public_amount INTEGER,
  salary_public_currency TEXT,
  negotiation_floor    INTEGER,
  created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_profiles_user ON profiles(user_id);

CREATE TABLE achievements (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  profile_id INTEGER NOT NULL REFERENCES profiles(id),
  metric     TEXT NOT NULL,
  context    TEXT,
  role       TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_achievements_profile ON achievements(profile_id);

CREATE TABLE style_profile (
  id             INTEGER PRIMARY KEY,
  user_id        INTEGER NOT NULL REFERENCES users(id),
  profile_id     INTEGER NOT NULL UNIQUE REFERENCES profiles(id),
  writing_sample TEXT,
  directives     TEXT,   -- JSON
  created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
"""

# external_applications: hand/external applies (LinkedIn Easy Apply,
# apply-by-email, web forms) outside any ATS pipeline. UNIQUE(user_id,
# dedup_hash) makes record_application idempotent. finding_id is a plain column
# now (no FK) — the FK to explore_findings is added in S2 when that table
# exists, via the FK-recreate migration pattern.
_EXTERNAL_APPS_SQLITE = """
CREATE TABLE external_applications (
  id           INTEGER PRIMARY KEY,
  user_id      INTEGER NOT NULL REFERENCES users(id),
  finding_id   INTEGER,
  url          TEXT,
  company_name TEXT,
  title        TEXT,
  channel      TEXT NOT NULL,
  method       TEXT,
  dedup_hash   TEXT NOT NULL,
  applied_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  notes        TEXT,
  UNIQUE(user_id, dedup_hash)
);
CREATE INDEX idx_extapp_user ON external_applications(user_id);
"""

# explore_findings: browser-scouted postings (the hunt pipeline's store) — the
# second cross-pipeline dedup + "match" source alongside external_applications.
# This migration also finally adds external_applications.finding_id's FK to
# explore_findings (deferred in S1.4): SQLite can only add the constraint by
# recreating the table. external_applications has no FK children, so the
# recreate needs no foreign-key toggle; existing finding_id values are all NULL.
_FINDINGS_SQLITE = """
CREATE TABLE explore_findings (
  id              INTEGER PRIMARY KEY,
  user_id         INTEGER NOT NULL REFERENCES users(id),
  source_slug     TEXT NOT NULL,
  dedup_hash      TEXT NOT NULL,
  url             TEXT NOT NULL,
  title           TEXT NOT NULL,
  company_name    TEXT,
  location        TEXT,
  remote_scope    TEXT,
  salary_text     TEXT,
  description     TEXT,
  score           INTEGER,
  score_breakdown TEXT,   -- JSON
  status          TEXT NOT NULL DEFAULT 'new',
  action          TEXT,
  first_seen      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  last_seen       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  UNIQUE(user_id, dedup_hash)
);
CREATE INDEX idx_findings_user ON explore_findings(user_id);
CREATE INDEX idx_findings_score ON explore_findings(score DESC);

CREATE TABLE external_applications_new (
  id           INTEGER PRIMARY KEY,
  user_id      INTEGER NOT NULL REFERENCES users(id),
  finding_id   INTEGER REFERENCES explore_findings(id),
  url          TEXT,
  company_name TEXT,
  title        TEXT,
  channel      TEXT NOT NULL,
  method       TEXT,
  dedup_hash   TEXT NOT NULL,
  applied_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  notes        TEXT,
  UNIQUE(user_id, dedup_hash)
);
INSERT INTO external_applications_new
  (id, user_id, finding_id, url, company_name, title,
   channel, method, dedup_hash, applied_at, notes)
  SELECT id, user_id, finding_id, url, company_name, title,
         channel, method, dedup_hash, applied_at, notes
  FROM external_applications;
DROP TABLE external_applications;
ALTER TABLE external_applications_new RENAME TO external_applications;
CREATE INDEX idx_extapp_user ON external_applications(user_id);
"""

# generated_assets: versioned drafts (cv/cover_letter) the client LLM produced
# against a finding. Version series per (user, finding, asset_type).
_ASSETS_SQLITE = """
CREATE TABLE generated_assets (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  finding_id INTEGER NOT NULL REFERENCES explore_findings(id),
  asset_type TEXT NOT NULL,
  content    TEXT NOT NULL,
  version    INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  UNIQUE(user_id, finding_id, asset_type, version)
);
CREATE INDEX idx_assets_finding ON generated_assets(finding_id);
"""

# applications: the browser-apply orchestration sessions (state machine), plus
# profiles.form_answers — the progressive Q&A store resolve_field saves to.
_APPLICATIONS_SQLITE = """
CREATE TABLE applications (
  id            INTEGER PRIMARY KEY,
  user_id       INTEGER NOT NULL REFERENCES users(id),
  finding_id    INTEGER NOT NULL REFERENCES explore_findings(id),
  state         TEXT NOT NULL DEFAULT 'draft',
  apply_method  TEXT,
  consent_level INTEGER NOT NULL DEFAULT 0,
  steps         TEXT,   -- JSON step plan
  current_step  INTEGER NOT NULL DEFAULT 0,
  outcome       TEXT,
  evidence      TEXT,
  created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_applications_user ON applications(user_id);
CREATE INDEX idx_applications_finding ON applications(finding_id);

ALTER TABLE profiles ADD COLUMN form_answers TEXT;
"""

MIGRATIONS: dict[int, str] = {
    2: _PROFILES_SQLITE,
    3: _EXTERNAL_APPS_SQLITE,
    4: _FINDINGS_SQLITE,
    5: _ASSETS_SQLITE,
    6: _APPLICATIONS_SQLITE,
    7: """
CREATE TABLE playbook_reports (
  id          INTEGER PRIMARY KEY,
  user_id     INTEGER NOT NULL REFERENCES users(id),
  source_slug TEXT NOT NULL,
  kind        TEXT NOT NULL,
  diff        TEXT,   -- JSON: what worked / moved / broke
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_playbook_reports_source ON playbook_reports(source_slug);
""",
    8: """
CREATE TABLE magic_link_tokens (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  token_hash TEXT NOT NULL UNIQUE,   -- sha256 hex of the raw token; raw never stored
  expires_at INTEGER NOT NULL,       -- Unix epoch seconds (dialect-uniform, tz-free)
  used_at    INTEGER,                -- Unix epoch when redeemed; NULL = unused
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
""",
    # sessions: the dashboard session store (S6.6c). Unlike magic_link_tokens
    # this IS a per-user RLS table on Postgres — every access happens with the
    # tenant context set (the API sets it from the signed cookie before the
    # session lookup). revoked_at NULL = active.
    9: """
CREATE TABLE sessions (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER NOT NULL REFERENCES users(id),
  user_agent TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  last_seen  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  revoked_at TEXT
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
""",
    # autopilot L1 (S7.2a, ADR 0005): the recorded human approval for one
    # application's submit. Written ONLY by services/autopilot.py behind the
    # session-authenticated API — never by the MCP entrypoint.
    10: """
ALTER TABLE applications ADD COLUMN submit_approved_at TEXT;
ALTER TABLE applications ADD COLUMN submit_approved_via TEXT;
""",
    # autopilot L2 (S7.2b, ADR 0005): the recorded autopilot policy. Append-only
    # — a PUT inserts a new row and revokes the prior active one; revocation
    # sets revoked_at. Active = newest row with revoked_at IS NULL. Written
    # ONLY by services/autopilot.py behind the session-authenticated API.
    11: """
CREATE TABLE autopilot_policy (
  id          INTEGER PRIMARY KEY,
  user_id     INTEGER NOT NULL REFERENCES users(id),
  enabled     INTEGER NOT NULL DEFAULT 1,
  min_score   INTEGER NOT NULL,
  max_per_day INTEGER NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  revoked_at  TEXT
);
CREATE INDEX idx_autopilot_policy_user ON autopilot_policy(user_id);
""",
}

# Migrations whose script recreates a table that FK children reference; these
# run with foreign-key enforcement toggled off around the script.
_FK_RECREATE_MIGRATIONS: frozenset[int] = frozenset()

# Postgres migration file -> version registered in schema_migrations. The file
# ordinal is the version here (unlike the donor's legacy offset).
_PG_MIGRATION_VERSIONS: dict[str, int] = {
    "001_initial.sql": 1,
    "002_profiles.sql": 2,
    "003_external_applications.sql": 3,
    "004_findings.sql": 4,
    "005_assets.sql": 5,
    "006_applications.sql": 6,
    "007_playbook_reports.sql": 7,
    "008_magic_link_tokens.sql": 8,
    "009_sessions.sql": 9,
    "010_applications_submit_approval.sql": 10,
    "011_autopilot_policy.sql": 11,
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
