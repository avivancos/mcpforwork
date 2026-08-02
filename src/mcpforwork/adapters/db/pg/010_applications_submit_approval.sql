-- applications.submit_approved_at / submit_approved_via (schema_migrations
-- version 10) — Postgres twin of MIGRATIONS[10]. Idempotent.
--
-- Autopilot L1 (S7.2a, ADR 0005): the recorded human approval for one
-- application's submit. Written ONLY by services/autopilot.py behind the
-- session-authenticated API — never by the MCP entrypoint. The applications
-- table is already RLS-forced (006), so the columns inherit tenant isolation.

ALTER TABLE applications ADD COLUMN IF NOT EXISTS submit_approved_at TIMESTAMP;
ALTER TABLE applications ADD COLUMN IF NOT EXISTS submit_approved_via TEXT;

INSERT INTO schema_migrations (version) VALUES (10) ON CONFLICT (version) DO NOTHING;
