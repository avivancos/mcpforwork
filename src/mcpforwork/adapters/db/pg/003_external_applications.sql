-- external_applications (schema_migrations version 3) — Postgres twin of
-- MIGRATIONS[3]. Single source of truth for hand/external applies outside any
-- ATS pipeline, so check_seen / record_application dedup across pipelines.
-- UNIQUE(user_id, dedup_hash) makes record_application idempotent. Per-user
-- table -> FORCE RLS with the fail-closed per-tenant policy. finding_id has no
-- FK yet (explore_findings arrives in S2).

CREATE TABLE IF NOT EXISTS external_applications (
  id           BIGSERIAL PRIMARY KEY,
  user_id      BIGINT NOT NULL REFERENCES users(id),
  finding_id   BIGINT,
  url          TEXT,
  company_name TEXT,
  title        TEXT,
  channel      TEXT NOT NULL,
  method       TEXT,
  dedup_hash   TEXT NOT NULL,
  applied_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  notes        TEXT,
  UNIQUE(user_id, dedup_hash)
);
CREATE INDEX IF NOT EXISTS idx_extapp_user ON external_applications(user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON external_applications TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;

ALTER TABLE external_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE external_applications FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_user_policy ON external_applications;
CREATE POLICY rls_user_policy ON external_applications
  USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)
  WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint);

INSERT INTO schema_migrations (version) VALUES (3) ON CONFLICT (version) DO NOTHING;
