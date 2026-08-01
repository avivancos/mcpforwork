# Auth — magic-link + session core and HTTP layer

> Passwordless auth for the dashboard API: a single-use magic-link token
> (hash-only at rest) is redeemed for an HMAC-signed session cookie backed by a
> server-side `sessions` store. Built by S6.6c (session store + `_current_user`
> DB check), S6.1b (Starlette HTTP layer), S6.1a (pure core).

## How it works

**Pure core** — `src/mcpforwork/services/auth_session.py`. Clock (`now`) and
signing `secret` are injected; the module holds no global state.

- `request_magic_link(uow, email, *, now, ttl_minutes=15)` (auth_session.py:48):
  normalizes the email (strip/lower), rejects control chars and interior
  whitespace (CR/LF SMTP header-injection guard, auth_session.py:57), then
  find-or-creates the `users` row. The raw token is `secrets.token_urlsafe(32)`;
  only its sha256 hex is persisted (`_hash_token`, auth_session.py:40) with an
  epoch expiry. The RAW token is returned once for the caller to deliver — it
  is never stored.
- `redeem_magic_link(uow, raw_token, *, now)` (auth_session.py:78): looks the
  token up by hash, rejects unknown/used/expired (`expires_at <= now`), then
  marks it used with an atomic `UPDATE ... WHERE used_at IS NULL` guard
  (auth_session.py:94) so a concurrent second redemption affects zero rows.
- `issue_session(uow, user_id, *, secret, now, max_age_s, user_agent)`
  (auth_session.py:103): inserts a `sessions` row (created_at/last_seen written
  explicitly from the injected clock in isoformat) and signs
  `{"uid", "sid", "exp"}` with itsdangerous `URLSafeSerializer` and the fixed
  salt `mcpforwork.session.v1` (auth_session.py:36). `exp` is ABSOLUTE — the
  lifetime is fixed at issue and cannot be widened by a lax reader. Default
  max age is 14 days (auth_session.py:37).
- `read_session(value, *, secret, now)` (auth_session.py:130): returns
  `{"uid", "sid"}` or `None` on tamper, wrong secret, malformed payload,
  non-dict payload, bool/non-int uid (`type() is int`), or at/past expiry
  (fail-closed `>=`). Pre-session-store cookies decode with `sid=None` and must
  be treated as logged out.
- Session store: `get_session` (auth_session.py:154), `touch_session` bumps
  `last_seen` but never on a revoked row (auth_session.py:159),
  `list_sessions` returns active sessions newest-seen first
  (auth_session.py:168), `revoke_session` is idempotent and returns False for
  unknown/foreign/already-revoked indistinguishably (auth_session.py:177).

**Schema** — `magic_link_tokens` (migration v8: SQLite
`adapters/db/migrations.py:226`, PG `adapters/db/pg/008_magic_link_tokens.sql`)
stores `token_hash` UNIQUE + epoch `expires_at`/`used_at`. It is NOT
RLS-forced: the lookup by `token_hash` happens pre-auth, before any user
context exists (same class as `users`/`audit_log`); the PG `app` role gets
SELECT/INSERT/UPDATE. `sessions` (migration v9: `migrations.py:240`, PG
`pg/009_sessions.sql`) IS per-user RLS-forced (FORCE RLS + USING/WITH CHECK
policy on `app.current_user_id`, pg/009_sessions.sql:23-28) — every access
happens with the tenant context set.

**HTTP layer** — `src/mcpforwork/entrypoints/api/app.py`:

- `POST /v1/auth/magic-link` (app.py:244): validates a JSON object body
  (non-dict → 400), calls `request_magic_link`, and delivers the link via the
  `Mailer` port (default `ConsoleMailer`). The link origin comes from
  `MCPFORWORK_PUBLIC_BASE_URL`, never the spoofable Host header
  (`_public_base_url`, app.py:159); the NORMALIZED email is delivered, not raw
  client input. Answers a uniform 202 `{"ok": true}` — the token is never in
  the response body, and errors do not disclose whether an email is valid.
- `GET /v1/auth/redeem?token=…` (app.py:268): redeems, sets the user context
  on the connection BEFORE minting the session row (sessions is RLS-forced),
  then sets the cookie `mcpforwork_session` with `HttpOnly`, `SameSite=Lax`,
  `Secure` (default; see hardening doc), `path=/`, 14-day max-age. Redirects
  302 to the fixed-config `MCPFORWORK_POST_LOGIN_REDIRECT` when set
  (`config.post_login_redirect`, config.py:53), else JSON `{"ok": true}`.
- `_current_user(request, uow)` (app.py:190): reads the signed cookie, then
  verifies the server-side store — sets the RLS context from the SIGNED uid
  first (so the session lookup runs inside the tenant wall), and refuses
  (None → 401) missing/tampered/expired cookies, sid-less legacy cookies,
  revoked or foreign sessions, and deleted users (closes the SQLite
  rowid-reuse hole). Touches `last_seen` and commits that bookkeeping
  independently before the route's own work starts (app.py:213-216).
- `_authed(request)` (app.py:230) is the per-route seam: an open UnitOfWork
  plus the resolved session, mirroring the MCP server's `_tenant_uow`.
- `_session_secret()` (app.py:150) is fail-closed: an unset
  `MCPFORWORK_SESSION_SECRET` raises rather than minting a guessable session.

## Design decisions

- **itsdangerous over hand-rolled HMAC** — the one new dependency, justified on
  the card: do not hand-roll signed-cookie crypto for a security boundary. The
  card originally sketched `URLSafeTimedSerializer`; the shipped code uses
  `URLSafeSerializer` with an explicit absolute `exp` embedded at issue (a
  gate fix — a reader-side `max_age` would fail open on lifetime).
- **Server-side session store (S6.6c)** — a signed cookie alone cannot be
  killed; the `sid` lets the API revoke sessions and die with account
  deletion. Legacy sid-less cookies are rejected, forcing re-login.
- **`/v1/account/delete` takes no confirm body** — the web consumer POSTs
  bodyless and the dashboard gates with its own "type DELETE" modal; the
  authed POST IS the confirmation. CSRF is covered by `SameSite=Lax`; a
  body-confirm would break the contract without stopping XSS. Delete also
  clears the session cookie (app.py:523-533).
- **Starlette over FastAPI** — ADR 0004 (amends ADR 0002): Starlette+uvicorn
  are already transitive via `mcp`, zero new runtime deps, and the httpx-backed
  TestClient gives real zero-mock HTTP tests.

## Testing

- `tests/test_auth_session.py` (16 tests, SQLite at tmp_path): single-use
  (incl. across separate connections), exact-instant expiry for both token and
  session, tamper/wrong-secret/garbage/wrong-shaped payloads, raw token never
  persisted, legacy-cookie `sid=None`, migration v8/v9 shape.
- `tests/test_auth_session_live.py` (live PG): pre-auth request/redeem with no
  user context as the `app` role, PG expiry, sessions INSERT rejected without
  context (WITH CHECK), tenant scoping under RLS.
- `tests/test_api_auth.py` (TestClient, real httpx, zero mocks): full
  magic-link → cookie → authed-request flow, hardened cookie flags, token
  never leaked, two-user isolation, fail-closed secret, non-object body → 400,
  control-char email rejected, configured-origin link (not Host header),
  delete clears the cookie, entrypoint-independence import contract.
- Mutant record on the S6.1a card: dropping the atomic single-use guard,
  storing the raw token, and flipping the expiry comparisons were all KILLED
  by named tests.

## Gotchas

- `now` must be timezone-aware UTC — `now.timestamp()` treats a naive datetime
  as local time and corrupts expiry across machines (module docstring,
  auth_session.py:19-21).
- The signed cookie is signed, NOT encrypted — keep only `{uid, sid, exp}` in
  it.
- `issue_session` writes `created_at`/`last_seen` explicitly in isoformat: the
  SQLite strftime default's `...Z` suffix would misorder against isoformat's
  `...+00:00` in lexicographic ORDER BY (auth_session.py:118-121).
- `read_session` rejects `bool` uids via `type() is int` — `bool` subclasses
  `int` (auth_session.py:145-146).
- On Postgres the caller MUST set the user context before `issue_session` —
  the redeem route does this right after redemption (app.py:277).
- Deferred to the hosted track (recorded on S6.1a/S6.1b, re-scoped by S6.1c):
  magic-link rate limiting, timing-uniform responses, CSRF tokens + `__Host-`
  prefix, token-in-logs hygiene, secret-manager wiring + rotation runbook.
