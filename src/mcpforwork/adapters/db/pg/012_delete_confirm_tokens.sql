-- delete_confirm_tokens (schema_migrations version 12) — Postgres twin of
-- MIGRATIONS[12]. FORCE RLS, fail-closed. Idempotent.
--
-- delete_my_data two-step (S7.2d): single-use confirm tokens for GDPR
-- erasure, minted and redeemed by services/privacy.py. A DEDICATED table,
-- not magic_link_tokens — mixing token kinds would let a login token replay
-- as a delete confirmation (and vice versa). Unlike magic_link_tokens this
-- table IS row-level-security-forced: tokens are only ever minted/redeemed
-- inside an authenticated tenant context (the MCP tool's per-user UoW), so
-- RLS makes a cross-tenant token invisible (redeem sees "no row" → invalid
-- token) and the service's user_id check is defense in depth. Only the
-- sha256 HASH is stored; expires_at/used_at are Unix epoch seconds
-- (dialect-uniform, timezone-free), matching the SQLite twin.

CREATE TABLE IF NOT EXISTS delete_confirm_tokens (
  id         BIGSERIAL PRIMARY KEY,
  user_id    BIGINT NOT NULL REFERENCES users(id),
  token_hash TEXT NOT NULL UNIQUE,
  expires_at BIGINT NOT NULL,
  used_at    BIGINT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_delete_confirm_tokens_user ON delete_confirm_tokens(user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON delete_confirm_tokens TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;

ALTER TABLE delete_confirm_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE delete_confirm_tokens FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_user_policy ON delete_confirm_tokens;
CREATE POLICY rls_user_policy ON delete_confirm_tokens
  USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)
  WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint);

INSERT INTO schema_migrations (version) VALUES (12) ON CONFLICT (version) DO NOTHING;
