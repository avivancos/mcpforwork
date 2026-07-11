-- magic_link_tokens (schema_migrations version 8) — Postgres twin of
-- MIGRATIONS[8]. Idempotent.
--
-- Deliberately NOT row-level-security-forced: this table is looked up by
-- token_hash DURING login, BEFORE any user context exists (there is no
-- authenticated tenant yet to scope by). Like `users` and `audit_log`, it is a
-- pre-auth table. Only the sha256 HASH of the raw token is stored; the raw
-- token is returned to the caller once and never persisted. expires_at/used_at
-- are Unix epoch seconds (dialect-uniform, timezone-free) to match the SQLite
-- twin and keep the freshness comparison identical on both backends.

CREATE TABLE IF NOT EXISTS magic_link_tokens (
  id         BIGSERIAL PRIMARY KEY,
  user_id    BIGINT NOT NULL REFERENCES users(id),
  token_hash TEXT NOT NULL UNIQUE,
  expires_at BIGINT NOT NULL,
  used_at    BIGINT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

GRANT SELECT, INSERT, UPDATE, DELETE ON magic_link_tokens TO app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app;

INSERT INTO schema_migrations (version) VALUES (8) ON CONFLICT (version) DO NOTHING;
