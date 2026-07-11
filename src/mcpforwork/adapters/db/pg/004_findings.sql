-- explore_findings (schema_migrations version 4) — the hunt pipeline's store,
-- Postgres twin of MIGRATIONS[4]. Per-user table -> FORCE RLS. Also adds the
-- external_applications.finding_id FK deferred in S1.4 (idempotent via a
-- pg_constraint guard). RLS on external_applications is untouched by ADD
-- CONSTRAINT, so the S1 fail-closed test still holds.

CREATE TABLE IF NOT EXISTS explore_findings (
  id              BIGSERIAL PRIMARY KEY,
  user_id         BIGINT NOT NULL REFERENCES users(id),
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
  score_breakdown TEXT,
  status          TEXT NOT NULL DEFAULT 'new',
  action          TEXT,
  first_seen      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, dedup_hash)
);
CREATE INDEX IF NOT EXISTS idx_findings_user ON explore_findings(user_id);
CREATE INDEX IF NOT EXISTS idx_findings_score ON explore_findings(score DESC);

GRANT SELECT, INSERT, UPDATE, DELETE ON explore_findings TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;

ALTER TABLE explore_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE explore_findings FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_user_policy ON explore_findings;
CREATE POLICY rls_user_policy ON explore_findings
  USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)
  WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint);

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'external_applications_finding_id_fkey'
  ) THEN
    ALTER TABLE external_applications
      ADD CONSTRAINT external_applications_finding_id_fkey
      FOREIGN KEY (finding_id) REFERENCES explore_findings(id);
  END IF;
END $$;

INSERT INTO schema_migrations (version) VALUES (4) ON CONFLICT (version) DO NOTHING;
