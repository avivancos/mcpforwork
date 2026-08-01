-- sessions (schema_migrations version 9) — Postgres twin of MIGRATIONS[9].
-- FORCE RLS, fail-closed. Idempotent.
--
-- The dashboard session store (S6.6c). Unlike magic_link_tokens this IS a
-- per-user RLS table: every access happens with `app.current_user_id` set —
-- the API sets it from the SIGNED cookie before the session lookup, and the
-- redeem route sets it right after a successful token redemption (the user
-- has just proved the identity the session is minted for).

CREATE TABLE IF NOT EXISTS sessions (
  id         BIGSERIAL PRIMARY KEY,
  user_id    BIGINT NOT NULL REFERENCES users(id),
  user_agent TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_seen  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revoked_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON sessions TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;

ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sessions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_user_policy ON sessions;
CREATE POLICY rls_user_policy ON sessions
  USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)
  WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint);

INSERT INTO schema_migrations (version) VALUES (9) ON CONFLICT (version) DO NOTHING;
