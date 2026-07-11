-- applications + profiles.form_answers (schema_migrations version 6) —
-- Postgres twin of MIGRATIONS[6]. FORCE RLS, fail-closed. Idempotent.

CREATE TABLE IF NOT EXISTS applications (
  id            BIGSERIAL PRIMARY KEY,
  user_id       BIGINT NOT NULL REFERENCES users(id),
  finding_id    BIGINT NOT NULL REFERENCES explore_findings(id),
  state         TEXT NOT NULL DEFAULT 'draft',
  apply_method  TEXT,
  consent_level INTEGER NOT NULL DEFAULT 0,
  steps         TEXT,
  current_step  INTEGER NOT NULL DEFAULT 0,
  outcome       TEXT,
  evidence      TEXT,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_applications_user ON applications(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_finding ON applications(finding_id);

ALTER TABLE profiles ADD COLUMN IF NOT EXISTS form_answers TEXT;

GRANT SELECT, INSERT, UPDATE, DELETE ON applications TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;

ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_user_policy ON applications;
CREATE POLICY rls_user_policy ON applications
  USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)
  WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint);

INSERT INTO schema_migrations (version) VALUES (6) ON CONFLICT (version) DO NOTHING;
