# Account API

> The dashboard's account pages: sessions list/revoke, audit trail, connection
> status, and honest self-host subscription/billing stubs — plus the
> server-side session store that `_current_user` enforces. Built by S6.6c
> (which pulled the session-revocation control forward from the hardening
> backlog).

## How it works

**Routes** — `src/mcpforwork/entrypoints/api/app.py`, all behind `_authed`
(401 without a live session):

- `GET /v1/sessions` (app.py:431): the user's active sessions via
  `auth_session.list_sessions`, shaped as SessionInfo — string `id`, `device`
  from `user_agent` ("Unknown device" fallback), `lastSeen`, and a `current`
  flag comparing against the cookie's `sid`.
- `POST /v1/sessions/{id}/revoke` (app.py:448): `auth_session.revoke_session`
  (idempotent; unknown/foreign/already-revoked → 404 indistinguishably).
  Revoking the CURRENT session also deletes the cookie, logging this browser
  out (app.py:461-463).
- `GET /v1/audit` (app.py:466) → `audit.recent(uow, user_id)`
  (services/audit.py:33): the user's own audit rows, newest first, capped at
  100, as `{at, event}` pairs; a `summary` key in the detail JSON is appended
  to the event text. `audit_log` is NOT RLS-forced — the explicit `user_id`
  filter is the tenant wall. `_iso` (audit.py:16) normalizes `created_at` to
  ISO-8601 on both dialects (SQLite stores ISO text; Postgres returns
  datetime).
- `GET /v1/connection` (app.py:472): derived from the user's LAST audit row —
  the only signal the server has, since it never sees the MCP transport.
  `connected` is `age <= _CONNECTED_WINDOW_S` (24h, app.py:61); `client` is
  always None (the API cannot know which agent connected); `syncedMinAgo` is
  whole minutes, or the honest sentinel `-1` when the user has never synced.
  `tenantEmail` is the CONFIGURED MCP tenant email
  (`config.local_user_email()`, config.py:45 — `MCPFORWORK_USER_EMAIL`,
  default `local@self-host`): if the human logged in with a different address,
  the tenant mismatch is visible right here (S6.8 alignment, ADR 0006).
- `GET /v1/subscription` (app.py:503): static honest stub
  `{"status": "active", "trialDaysLeft": 0, "price": "self-host"}` — no
  billing on self-host.
- `POST /v1/billing/session` (app.py:511): `{"url": null}` — Stripe is S7.1,
  deferred (hosted track out of scope).
- `POST /v1/account/export` / `POST /v1/account/delete` (app.py:517-533) →
  `privacy.export_user_data` / `privacy.delete_user_data`; delete also clears
  the session cookie so the deleted account can't keep presenting a still-valid
  signed cookie for its 14-day life.

**Session store enforcement** — `_current_user` (app.py:190) verifies the
cookie's `sid` against the `sessions` table on EVERY request: revoked session,
foreign session, deleted user, or legacy sid-less cookie all get 401. This
closes the deleted-user-cookie hole and the SQLite `users.id` rowid-reuse hole
(a recycled rowid has no live session rows, so the stale cookie dies at the
session lookup). See `docs/api/auth.md` for the store itself and the v9 schema
(SQLite `adapters/db/migrations.py:240`, PG `adapters/db/pg/009_sessions.sql`
with FORCE RLS + USING/WITH CHECK policy).

## Design decisions

- **Session revocation pulled forward** from the hardening card: the dashboard
  sessions page needs a real store, so S6.6c shipped it rather than stubbing.
- **Connection status is derived, never measured** — audit rows are the only
  MCP-activity signal the API has; the 24h window and `-1` sentinel are
  deliberate honest approximations (the web renders both).
- **`tenantEmail` is additive** — it surfaces self-host tenant mismatch
  (MCP writes as `MCPFORWORK_USER_EMAIL`; the human must log in with the same
  address) without breaking the existing web contract.
- **Stubs are honest, not fake-rich** — subscription/billing return static
  self-host truths instead of pretending a billing backend exists.

## Testing

`tests/test_account_api.py` (TestClient, zero mocks, 12 tests):

- All account routes require auth (401 matrix).
- Sessions list shows each login with the current one flagged; revoking the
  OTHER session kills its cookie (next request 401); revoking the CURRENT
  session clears the cookie; foreign revoke → 404; a deleted user's other
  sessions die.
- Audit lists the user's own rows newest first and never another user's.
- Connection reflects real activity and the tenant email (fresh user →
  `connected: false`, `syncedMinAgo: -1`).
- Subscription/billing stubs return the documented static shapes.
- Live-PG RLS arm in `tests/test_auth_session_live.py`:
  `test_sessions_insert_requires_the_user_context` (context-less INSERT
  rejected by WITH CHECK) and `test_sessions_are_tenant_scoped_under_rls`
  (user A cannot read/revoke B's rows as the `app` role).
- Migration proof: `test_migration_v9_creates_the_sessions_table`
  (tests/test_auth_session.py:214) plus live psql checks (FORCE RLS, policy,
  schema_migrations=9) recorded on the card.

## Gotchas

- `audit.recent` normalizes `at` via `_iso` — without it, Postgres leaks a
  space-separated `str(datetime)` shape instead of ISO-8601 (S6.6c gate P2
  fix).
- Session bookkeeping commits independently inside `_current_user`
  (app.py:213-216) — safe only because the route's own work has not started
  yet; never move that commit after route writes.
- Double-revoke returns 404 (idempotent, indistinguishable) — a P3 deferred on
  the card, along with sharpness tests for the 24h `connected` boundary, the
  100-row audit cap, and crafted unknown-sid cookies; revisit if a future card
  touches these paths.
- The audit cap is 100 rows (audit.py:33) — older events are simply not shown
  on the dashboard.
- `device` is the raw `user_agent` string — no parsing; "Unknown device" when
  absent.
