-- playbook_reports (schema_migrations version 7) — crowd-learning capture.
-- Postgres twin of MIGRATIONS[7]. FORCE RLS, fail-closed. Idempotent.

CREATE TABLE IF NOT EXISTS playbook_reports (
  id          BIGSERIAL PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users(id),
  source_slug TEXT NOT NULL,
  kind        TEXT NOT NULL,
  diff        TEXT,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_playbook_reports_source ON playbook_reports(source_slug);

GRANT SELECT, INSERT, UPDATE, DELETE ON playbook_reports TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;

ALTER TABLE playbook_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE playbook_reports FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_user_policy ON playbook_reports;
CREATE POLICY rls_user_policy ON playbook_reports
  USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)
  WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint);

INSERT INTO schema_migrations (version) VALUES (7) ON CONFLICT (version) DO NOTHING;
