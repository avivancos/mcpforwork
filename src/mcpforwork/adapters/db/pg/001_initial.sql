-- Postgres base schema (schema_migrations version 1) — the dialect twin of
-- schema.sql. All statements are idempotent (IF NOT EXISTS / ON CONFLICT /
-- DO $$ guard) so migrate_postgres can re-run this file safely.
--
-- `users` and `audit_log` are pre-auth / cross-cutting and are deliberately
-- NOT row-level-security-forced. Per-user domain tables (profiles,
-- external_applications, …) arrive in S1.3/S1.4 and enable RLS themselves.

CREATE TABLE IF NOT EXISTS schema_migrations (
  version    INTEGER PRIMARY KEY,
  applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Non-superuser application role that per-request connections authenticate as,
-- so FORCE row-level security applies to it. The password here is a dev/test
-- default; production deployments MUST override it:
--   ALTER ROLE app PASSWORD '<secure value>';
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app') THEN
    CREATE ROLE app WITH LOGIN PASSWORD 'app_secret' NOINHERIT;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS users (
  id         BIGSERIAL PRIMARY KEY,
  email      TEXT NOT NULL UNIQUE,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
  id         BIGSERIAL PRIMARY KEY,
  user_id    BIGINT REFERENCES users(id),
  action     TEXT NOT NULL,
  detail     TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON users TO app;
GRANT SELECT, INSERT, UPDATE, DELETE ON audit_log TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;

INSERT INTO schema_migrations (version) VALUES (1) ON CONFLICT (version) DO NOTHING;
