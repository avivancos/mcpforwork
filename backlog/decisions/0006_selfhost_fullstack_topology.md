# ADR 0006 — Self-host full-stack topology

**Status:** accepted (S6.8) · **Amends:** ADR 0003 (docker compose)

## Context

ADR 0003 shipped `docker-compose.yml` with two services (`mcp`, `web`) and the
dashboard on the in-memory fixture dataset because the parity API did not
exist. S6.6a/b/c built that API (Starlette, ADR 0004) and S6.1c hardened it
for self-host. The product's end state is one command — `docker compose up
--build` — booting the whole loop: dashboard on real data, parity API, and
the networked MCP connector, all over one SQLite volume.

Two design problems had no existing answer:

1. **Tenant alignment.** The MCP server writes as a local user
   (`MCPFORWORK_USER_ID`, historically id 1 with email `local@self-host`).
   The dashboard resolves users by magic-link find-or-create **on email**.
   If the human logs in with any other address, the dashboard shows a second,
   empty account while the MCP keeps writing to the first — a silent split.
2. **Login UX in compose.** The magic link redeems on the API origin
   (`api:8000`); the human's destination is the dashboard (`web:3000`, mapped
   to `localhost:2200`). The redeem response must hand the browser to the
   dashboard.

## Decision

1. **Three services, one volume.** `api` runs the same image as `mcp`
   (`uvicorn mcpforwork.entrypoints.api.app:app`), sharing `mcpforwork-data`.
   `web` gets `MCPFORWORK_API_URL=http://api:8000` and loses
   `MCPFORWORK_FIXTURES` — fixtures stay opt-in for the public demo only
   (ADR 0002's fail-closed guard untouched).
2. **Email-keyed tenant.** New `MCPFORWORK_USER_EMAIL` (default
   `local@self-host`) names the local user's email. The MCP server resolves
   its tenant **by email, find-or-create** — the same key the magic-link
   login uses — so both entrypoints land on one `users` row regardless of
   boot order. `MCPFORWORK_USER_ID` survives as an explicit pin
   (legacy/escape hatch); pin + conflicting email is a loud
   `RuntimeError`, never a silent second tenant. `GET /v1/connection`
   surfaces the configured email as `tenantEmail` so a mismatch is visible
   in the dashboard.
3. **Fixed-config post-login redirect.** `MCPFORWORK_POST_LOGIN_REDIRECT`
   (compose default `http://localhost:2200/pipeline`) turns redeem into a
   302 after the cookie is set. The target is server config, never a client
   parameter (open-redirect class closed by construction). Unset → the API
   keeps answering JSON 200 for API-only clients.
4. **Secret posture.** Compose requires `MCPFORWORK_SESSION_SECRET` from
   `.env` via the `:?` error syntax — no baked default (S6.1c).
5. **LAN-http cookie posture.** Compose sets `MCPFORWORK_COOKIE_SECURE=0`
   (S6.1c escape hatch): LAN http has no TLS, and a `Secure` cookie would
   never be stored, making login impossible. Flip to `1` behind a
   TLS-terminating reverse proxy. `MCPFORWORK_ALLOWED_HOSTS` defaults to
   `api,localhost,127.0.0.1` — `api` is the in-network name the web
   container fetches with.

## Consequences

- **Single-tenant caveat, accepted:** the networked MCP endpoint
  (streamable-http on `:8500`) has no per-connection authentication. Any
  process that can reach the port acts as the local user. Acceptable for
  single-user self-host on a trusted LAN (the threat model ADR 0003 already
  assumes); multi-tenant HTTP MCP auth is hosted scope and deliberately not
  built.
- SQLite on a shared volume is written by two processes (`mcp`, `api`).
  Both open with `busy_timeout` and short transactions; the single-writer
  pattern holds because writes are human-paced (tool calls, dashboard
  clicks). Postgres remains the multi-writer answer (hosted).
- The public demo deploy keeps working: it sets `MCPFORWORK_FIXTURES=1`
  explicitly and never sets `MCPFORWORK_API_URL`.
