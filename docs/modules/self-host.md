# Self-host full-stack topology (docker compose)

> One command — `docker compose up --build` — boots the whole self-host loop:
> the parity API (`api`), the networked MCP connector (`mcp`), and the
> dashboard (`web`) on real data, all over one shared SQLite volume. The same
> card aligned the MCP writer and the dashboard magic-link login on ONE
> `users` row (email-keyed tenant) and added the fixed-config post-login
> redirect so redeem lands the browser on the dashboard. Card: S6.8, built on
> the S6.6a/b/c parity API and S6.1c hardening. ADR:
> [0006](../../backlog/decisions/0006_selfhost_fullstack_topology.md) (amends
> ADR 0003).

## How it works

**Compose topology** (`docker-compose.yml`). Three services, one volume
`mcpforwork-data:/data` (line 116):

- `api` (`docker-compose.yml:59-90`) — same image as `mcp` (`mcpforwork-mcp`,
  line 63; one build, two entrypoints), runs `uvicorn
  mcpforwork.entrypoints.api.app:app --host 0.0.0.0 --port 8000` (line 79),
  host port `${API_PORT:-8000}`, shares the SQLite volume (lines 82-83). Env:
  `MCPFORWORK_SESSION_SECRET` REQUIRED via the compose `:?` error syntax
  (line 68) — no baked default, `docker compose config` fails clearly when
  unset (S6.1c posture); `MCPFORWORK_USER_EMAIL` (line 69);
  `MCPFORWORK_POST_LOGIN_REDIRECT` default `http://localhost:2200/pipeline`
  (line 71); `MCPFORWORK_COOKIE_SECURE=0` for LAN http (line 75 — flip to 1
  behind TLS); `MCPFORWORK_ALLOWED_HOSTS=api,localhost,127.0.0.1` (line 78) —
  `api` is mandatory: the web container fetches `http://api:8000` with
  `Host: api` and the S6.1c TrustedHost guard would 400 the BFF loop.
- `web` (`docker-compose.yml:92-114`) — live-wired:
  `MCPFORWORK_API_URL=http://api:8000` (line 101) and NO `MCPFORWORK_FIXTURES`
  (the demo dataset stays opt-in for the public site only; the ADR 0002
  fail-closed guard is untouched), `depends_on: api`, port `${WEB_PORT:-2200}`.
- `mcp` (`docker-compose.yml:21-57`) — streamable-http on :8500, carries the
  same `MCPFORWORK_USER_EMAIL` (line 29); the command sets `mcp.settings`
  before `run()` because FastMCP hard-codes the host (lines 35-43, Gotchas).
  Header comment (lines 12-18): the tenant-alignment rule + the single-tenant
  caveat — the networked MCP has no per-connection auth; anything reaching
  the port acts as the local user (multi-tenant HTTP MCP auth: hosted scope).

**Tenant alignment** (ADR 0006 decision 2). The dashboard resolves users by
magic-link find-or-create ON EMAIL; the MCP used to write as a pinned id —
any other login address silently split the tenant. Now both key on email:

- `config.local_user_email()` (`src/mcpforwork/config.py:45-50`) —
  `MCPFORWORK_USER_EMAIL`, default `local@self-host` (`config.py:30`).
- `config.local_user_id()` (`config.py:33-42`) — now `int | None`; unset
  means resolve-by-email, the pin is the escape hatch (only caller: MCP).
- `server._resolve_local_user` (`src/mcpforwork/entrypoints/mcp/server.py:50-80`),
  run on every `_uow()` boot (`server.py:83-92`): pin set + email unset → use
  the pinned row as-is (legacy); pin set + email set + row's email differs →
  loud `RuntimeError` ("unset one of them", lines 66-70), never a silent
  second tenant; otherwise find-or-create `users` BY EMAIL (lines 75-80) —
  the same key the magic-link login uses, so both entrypoints converge on one
  row regardless of boot order.
- `GET /v1/connection` surfaces the CONFIGURED tenant email as `tenantEmail`
  (`src/mcpforwork/entrypoints/api/app.py:478,490,499`) — not the session
  email (that S6.6c behavior was the placeholder) — so a login under a
  different address makes the mismatch visible in the payload.

**Post-login redirect** (ADR 0006 decision 3). The magic link redeems on the
API origin but the destination is the dashboard. `GET /v1/auth/redeem`
(`app.py:268-302`): after the session cookie is minted,
`config.post_login_redirect()` (`config.py:53-57`) — set → `302` to the fixed
configured URL with the cookie riding the response (`app.py:291-295`); unset
→ JSON `{"ok": true}` for API-only clients. The target is server config,
NEVER a client parameter — the open-redirect class is closed by construction.

**Operator contract** (`.env.example`): the required secret with a generator
one-liner (lines 4-6), `MCPFORWORK_USER_EMAIL` with the "log in with THIS
SAME address" rule (lines 8-11), and commented optional overrides — redirect,
cookie-secure, allowed hosts, host ports (lines 13-28). `cp .env.example
.env` + set the secret is the whole setup.

## Design decisions

- **Email as the tenant key, not the id.** Magic-link login was already
  email-keyed find-or-create; keying the MCP the same way makes boot order
  irrelevant (dashboard-first and MCP-first converge). Rejected alternative:
  keeping the id pin primary — it cannot converge with a row the dashboard
  already minted.
- **Pin kept, conflicts loud.** `MCPFORWORK_USER_ID` survives for legacy
  installs, but pin + conflicting email raises instead of picking a winner —
  a misconfiguration must fail at boot, not split data.
- **Fixed-config redirect.** A `?next=` parameter would be the classic open
  redirect; making the target compose config removes the whole class. Unset
  keeps JSON 200 so non-browser API clients are unaffected.
- **`api` shares the `mcp` image and the SQLite volume.** One Dockerfile, two
  entrypoints; single-writer holds because writes are human-paced (both
  processes open with `busy_timeout` + short transactions). Postgres remains
  the multi-writer answer (hosted).
- **Secret required, never baked; `COOKIE_SECURE=0` on LAN http** (S6.1c) —
  the `:?` syntax makes `docker compose config` itself the guard; LAN http
  cannot store a `Secure` cookie, so login requires 0 until TLS terminates
  (flip documented in compose + `.env.example`).
- ADRs: 0006 (this topology, amends 0003); 0002 (web fail-closed fixtures
  guard — deliberately untouched).

## Testing

- `tests/test_compose_stack.py` — 16 tests, zero mocks, no docker-in-test:
  - Compose SHAPE via parsed yaml (the declared dependency), not greps
    (`test_compose_stack.py:58-92`): api shares image+volume and runs
    uvicorn, web points at the real API with no FIXTURES flag, both Python
    services carry the tenant email, `.env.example` documents the contract.
    The secret check (`:70-74`) is raw-text by nature: `:?` present AND the
    `:-` baked-default form absent.
  - Redeem redirect (`:98-135`): 302 + cookie riding when configured; JSON
    200 when unset; **adversarial** `?next=http://evil...` never overrides
    the configured target (review P2 disposition — kills the client-override
    mutant).
  - `tenantEmail` (`:141-157`): reflects the configured email; defaults to
    `local@self-host` so a mismatched login is visible in the payload.
  - MCP boot alignment on real tmp SQLite (`:174-245`): find-or-create by
    email, idempotent second boot, dashboard-first boot-order convergence
    (the MCP finds the row the magic-link minted), explicit pin honored,
    pin+conflicting email raises, legacy pin keeps the row's existing email.
  - End-to-end same-row proof (`:248-267`): `auth_session.request_magic_link`
    (the dashboard login) and an MCP boot with the same email resolve the
    SAME `users.id`.
- `tests/test_account_api.py` — the `env` fixture is hermetic
  (`test_account_api.py:32-40`): `delenv` of `MCPFORWORK_USER_EMAIL` /
  `MCPFORWORK_POST_LOGIN_REDIRECT` so a developer shell cannot leak config
  into the `tenantEmail` assertion (review P2 disposition);
  `test_connection_reflects_real_activity_and_the_tenant_email` (`:190-196`)
  updated to the configured-email semantics.
- Manual gates observed at close (card DoD): `docker compose config` valid
  with the secret set, clear `:?` error without.

## Gotchas

- **`ALLOWED_HOSTS` must include `api`.** The web BFF fetches
  `http://api:8000` with `Host: api`; without it the S6.1c TrustedHost guard
  400s every dashboard call. A LAN hostname must be added to the list.
- **`tenantEmail` has no web UI consumer yet** (review P3, accepted): the
  mismatch is visible in the API payload only; dashboard wiring lands with
  the W6.x work. "Visible in the dashboard" overstates today's state.
- **Container quirks:** FastMCP's constructor hard-codes `host="127.0.0.1"`
  (overriding `FASTMCP_HOST`) — setting `mcp.settings.host` before `run()` is
  the supported path (compose `mcp` command); healthchecks probe `127.0.0.1`,
  not `localhost`, because alpine resolves `localhost` to `::1` first while
  the servers bind IPv4.
- **The pin+email conflict check only fires when the email was EXPLICITLY
  set** (`server.py:66`): a legacy pin with no `MCPFORWORK_USER_EMAIL` in the
  environment keeps the row's existing email untouched — do not "simplify"
  this into always comparing against the default, or legacy installs break.
- **Real browser-on-compose verification is the W6.1 demo gate** — the card
  deliberately did not duplicate it; tests stop at compose-shape + behavior.
- **Compose drift vs the W1.2 card text:** fixtures-on + commented API URL
  no longer exists on disk; host port is 2200, not 3000 (`modules/web.md`).
