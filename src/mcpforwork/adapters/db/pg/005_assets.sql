-- generated_assets (schema_migrations version 5) — Postgres twin of
-- MIGRATIONS[5]. Per-user table -> FORCE RLS, fail-closed policy. Idempotent.

CREATE TABLE IF NOT EXISTS generated_assets (
  id         BIGSERIAL PRIMARY KEY,
  user_id    BIGINT NOT NULL REFERENCES users(id),
  finding_id BIGINT NOT NULL REFERENCES explore_findings(id),
  asset_type TEXT NOT NULL,
  content    TEXT NOT NULL,
  version    INTEGER NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, finding_id, asset_type, version)
);
CREATE INDEX IF NOT EXISTS idx_assets_finding ON generated_assets(finding_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON generated_assets TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;

ALTER TABLE generated_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_assets FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_user_policy ON generated_assets;
CREATE POLICY rls_user_policy ON generated_assets
  USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)
  WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint);

INSERT INTO schema_migrations (version) VALUES (5) ON CONFLICT (version) DO NOTHING;
