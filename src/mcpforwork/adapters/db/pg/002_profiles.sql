-- Profiles, achievements, style_profile (schema_migrations version 2) — the
-- Postgres dialect twin of MIGRATIONS[2]. Idempotent (IF NOT EXISTS / DROP
-- POLICY IF EXISTS) so migrate_postgres can re-run it.
--
-- These are per-user tables, so each enables FORCE row-level security with the
-- same per-tenant policy proven in test_rls_live.py. The policy is written
-- inline per table by design: the migration runner applies static .sql files,
-- so there is no code seam to share; each table's isolation is re-verified live
-- in test_profiles_rls_live.py. NULLIF(...) -> NULL on an unset GUC, so an
-- unbound session matches no rows (fail-closed).

CREATE TABLE IF NOT EXISTS profiles (
  id                     BIGSERIAL PRIMARY KEY,
  user_id                BIGINT NOT NULL REFERENCES users(id),
  label                  TEXT NOT NULL DEFAULT 'default',
  is_active              INTEGER NOT NULL DEFAULT 1,
  full_name              TEXT,
  contact_email          TEXT,
  country                TEXT,
  city                   TEXT,
  work_auth_countries    TEXT,
  needs_sponsorship      INTEGER,
  target_titles          TEXT,
  sectors                TEXT,
  seniority              TEXT,
  employment_types       TEXT,
  work_modes             TEXT,
  relocation             INTEGER,
  min_salary_amount      INTEGER,
  min_salary_currency    TEXT,
  min_salary_period      TEXT,
  languages              TEXT,
  cv_text                TEXT,
  links                  TEXT,
  availability_date      TEXT,
  notice_period          TEXT,
  deal_breakers          TEXT,
  career_narrative       TEXT,
  salary_public_amount   INTEGER,
  salary_public_currency TEXT,
  negotiation_floor      INTEGER,
  created_at             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_profiles_user ON profiles(user_id);

CREATE TABLE IF NOT EXISTS achievements (
  id         BIGSERIAL PRIMARY KEY,
  user_id    BIGINT NOT NULL REFERENCES users(id),
  profile_id BIGINT NOT NULL REFERENCES profiles(id),
  metric     TEXT NOT NULL,
  context    TEXT,
  role       TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_achievements_profile ON achievements(profile_id);

CREATE TABLE IF NOT EXISTS style_profile (
  id             BIGSERIAL PRIMARY KEY,
  user_id        BIGINT NOT NULL REFERENCES users(id),
  profile_id     BIGINT NOT NULL UNIQUE REFERENCES profiles(id),
  writing_sample TEXT,
  directives     TEXT,
  created_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

GRANT SELECT, INSERT, UPDATE, DELETE ON profiles TO app;
GRANT SELECT, INSERT, UPDATE, DELETE ON achievements TO app;
GRANT SELECT, INSERT, UPDATE, DELETE ON style_profile TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_user_policy ON profiles;
CREATE POLICY rls_user_policy ON profiles
  USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)
  WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint);

ALTER TABLE achievements ENABLE ROW LEVEL SECURITY;
ALTER TABLE achievements FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_user_policy ON achievements;
CREATE POLICY rls_user_policy ON achievements
  USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)
  WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint);

ALTER TABLE style_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE style_profile FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_user_policy ON style_profile;
CREATE POLICY rls_user_policy ON style_profile
  USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)
  WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint);

INSERT INTO schema_migrations (version) VALUES (2) ON CONFLICT (version) DO NOTHING;
