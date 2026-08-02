-- autopilot_policy (schema_migrations version 11) — Postgres twin of
-- MIGRATIONS[11]. FORCE RLS, fail-closed. Idempotent.
--
-- Autopilot L2 (S7.2b, ADR 0005): the recorded autopilot policy. Append-only
-- — a PUT inserts a new row and revokes the prior active one; revocation sets
-- revoked_at. Active = newest row with revoked_at IS NULL. Written ONLY by
-- services/autopilot.py behind the session-authenticated API — never by the
-- MCP entrypoint. Per-user table: every access happens with
-- `app.current_user_id` set.

CREATE TABLE IF NOT EXISTS autopilot_policy (
  id          BIGSERIAL PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users(id),
  enabled     BOOLEAN NOT NULL DEFAULT TRUE,
  min_score   INTEGER NOT NULL,
  max_per_day INTEGER NOT NULL,
  created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  revoked_at  TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_autopilot_policy_user ON autopilot_policy(user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON autopilot_policy TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;

ALTER TABLE autopilot_policy ENABLE ROW LEVEL SECURITY;
ALTER TABLE autopilot_policy FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_user_policy ON autopilot_policy;
CREATE POLICY rls_user_policy ON autopilot_policy
  USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)
  WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint);

INSERT INTO schema_migrations (version) VALUES (11) ON CONFLICT (version) DO NOTHING;
