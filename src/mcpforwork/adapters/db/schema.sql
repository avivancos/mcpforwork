-- Base schema, SQLite dialect (PRAGMA user_version = 1).
-- Per-user domain tables (profiles, applications, ...) arrive as migrations in
-- S1.3/S1.4. `users` and `audit_log` are pre-auth / cross-cutting and are
-- deliberately NOT row-level-security-forced when the Postgres RLS migration
-- lands in S1.2.

CREATE TABLE users (
  id         INTEGER PRIMARY KEY,
  email      TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE audit_log (
  id         INTEGER PRIMARY KEY,
  user_id    INTEGER REFERENCES users(id),
  action     TEXT NOT NULL,
  detail     TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX idx_audit_log_user ON audit_log(user_id);
