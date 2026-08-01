# API hardening (self-host)

> Edge protections on the Starlette parity API, scoped to self-host terms:
> body-size cap, TrustedHost allowlist, cookie-Secure escape hatch, and the
> restricted-PG-role request path. Built by S6.1c (which replaced the
> hosted-oriented hardening card; each originally-deferred control was either
> implemented or re-deferred in writing).

## How it works

All in `src/mcpforwork/entrypoints/api/app.py` unless noted.

- **Body-size cap** — `_BodySizeCap` (app.py:69), a pure-ASGI middleware
  wrapping only body-carrying methods (`POST/PUT/PATCH`, app.py:66) with a
  64 KB cap (`_MAX_BODY_BYTES`, app.py:65). Fast path: a declared
  Content-Length over the cap is rejected without reading a byte
  (app.py:94-99). A length-less (chunked) body is buffered bounded at cap+1
  and replayed to the app as a single message; over the cap the middleware
  answers 413 `{"error": "payload too large"}` ITSELF (app.py:100-123). An
  unparseable Content-Length is treated as untrustworthy and falls to the
  buffered path (app.py:92). The unauthenticated magic-link POST buffers
  `await request.json()` — without the cap that is a memory-DoS vector.
- **TrustedHost allowlist** — `_allowed_hosts()` (app.py:126) drives
  `TrustedHostMiddleware` (outermost middleware, `www_redirect=False`,
  app.py:556-561): a spoofed Host is rejected 400 before any route or body
  read. Default is `localhost,127.0.0.1,testserver` (testserver is httpx's
  dummy host — never resolves, no DNS-rebinding surface).
  `MCPFORWORK_ALLOWED_HOSTS` (comma-separated) overrides to expose the API on
  a LAN hostname.
- **Cookie Secure flag** — `_cookie_secure()` (app.py:139): `Secure` on the
  session cookie by default; `MCPFORWORK_COOKIE_SECURE=0` is the documented
  escape hatch for LAN-http self-host (no TLS), where a Secure cookie is never
  stored and magic-link login could not work. HttpOnly/SameSite are untouched.
- **Restricted PG role on the request path** — `config.db_run_migrations()`
  (config.py:60, env `MCPFORWORK_DB_RUN_MIGRATIONS`, default 1) lets the API
  connect with `run_migrations=False` (`_connect`, app.py:224-227) so the
  restricted Postgres `app` role — which cannot run DDL — can serve requests;
  migrations are a deploy-time step for a privileged connection. Self-host
  SQLite keeps auto-migrate ergonomics.

## Design decisions

- **Buffer-and-answer-413, not raise-from-receive.** The routes' deliberate
  blanket `except Exception` around `request.json()` would swallow a raised
  signal and return 400 — the first implementation (raise + exception handler)
  failed exactly that way and the chunked test caught it. The middleware
  therefore answers 413 directly.
- **IPv6 `::1` deliberately absent from the default allowlist**:
  TrustedHostMiddleware splits the Host header on `:`, so a bracketed IPv6
  literal could never match — documented in `_allowed_hosts`.
- **`www_redirect=False`**: an API answers 400, it never redirects to www.
- **Re-deferred to the hosted track (written on the S6.1c card, with
  reasons):** magic-link rate limiting (only ConsoleMailer exists — no real
  sender to abuse on single-user self-host); host/origin fail-closed raise for
  non-Console mailers (no such mailer yet — dead code); CSRF tokens +
  `__Host-` cookie prefix (dashboard is same-origin fetch with
  `SameSite=Lax`+`HttpOnly`; `__Host-` requires `Secure`, which the LAN-http
  escape hatch turns off); timing-uniform magic-link responses (the
  account-existence oracle matters against a shared multi-tenant DB);
  token-in-logs hygiene / POST-confirm redeem interstitial (self-host logs
  live on the user's own machine; real UX cost).
- **Recorded as already done earlier, not reworked:** session revocation store
  + user-existence check (S6.6c); SQLite `users.id` rowid-reuse (closed by
  that same check — a recycled rowid has no live session rows); secret
  fail-closed raise (S6.1b; compose-side wiring rides S6.8).

## Testing

`tests/test_api_hardening.py` (zero mocks; TestClient + live-PG arm):

- Cap: declared-length over-cap → 413, chunked over-cap → 413, exact-64 KB
  boundary passes, GETs are not capped (app.py:83).
- Host: disallowed Host → 400; default allowlist serves local hosts; env
  override narrows/widens.
- Cookie: Secure present by default, absent under `MCPFORWORK_COOKIE_SECURE=0`.
- Live PG (`@pytest.mark.live`, Docker postgres:16-alpine): the fixture
  (test_api_hardening.py:155-168) points the API at the `app`-role URL with
  `MCPFORWORK_DB_RUN_MIGRATIONS=0`.
  `test_the_request_path_role_is_non_privileged` asserts the request-path role
  is the `app` role with `rolsuper=False` and `rolbypassrls=False` (fail-closed
  privilege assertion). `test_live_pg_cross_tenant_isolation_through_the_http_layer`
  performs two real magic-link logins and proves user A cannot read/act on
  user B via pipeline, match GET/approve/discard, audit, or sessions — while B
  sees his own data through the same stack (grants are correct).
- Behavior strictly strengthened, pre-existing test updated:
  `test_magic_link_url_uses_the_configured_origin_not_the_host_header`
  (tests/test_api_auth.py:166) used to assert a spoofed-Host request was
  SERVED with the config-origin link; TrustedHost now rejects it 400 pre-route
  (no token minted, no email sent) and the test asserts both layers.

## Gotchas

- Middleware order matters: TrustedHost is outermost so a spoofed Host dies
  before any body is read (app.py:557-558).
- A garbage (non-integer) Content-Length is not rejected outright — it falls
  through to the buffered path, which still enforces the cap (app.py:90-92).
- `http.disconnect` during a chunked read returns without serving
  (app.py:103-104) — the client is gone, nothing to answer.
- The 64 KB cap also bounds the UNAUTHENTICATED magic-link route; keep it in
  mind if a future route legitimately needs larger bodies (the cap is
  per-app, not per-route).
- Compose-side secret wiring (`require MCPFORWORK_SESSION_SECRET` from `.env`)
  stays on S6.8 — the app-side fail-closed raise already shipped in S6.1b.
