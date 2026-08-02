# Web surfaces (Next.js dashboard + public site)

> The `web/` app: marketing landing, docs site, legal/SEO pages, and the
> dashboard — a **mirror and control panel, never a workspace** (ADR 0002).
> Built API-contract-first on a typed seam, shipped on fixtures, live against
> the real parity API in compose since W6.1. Cards (latest first): W2.2, W6.1,
> S6.3, W5.2, W5.1, W4.1, W3.1, W2.1, W1.2, W1.1.

## How it works

**Stack.** Next.js 15 App Router + TypeScript, server components + native
`fetch`, plain CSS modules with custom-property tokens. No state library, no
component kit, no Tailwind; runtime deps are exactly `next`/`react`/`react-dom`
(`web/package.json:15`). Dark mode is dashboard-scoped (`[data-allow-dark]`);
landing/docs/legal are light-only by design.

**Routes.** Public: `/`, `/pricing`, `/faq`, `/docs` + 15 doc pages, `/privacy`,
`/terms`, `/security`. App group: `(flow)` = `/login`, `/connect`, `/onboarding`;
`(dash)` = `/pipeline`, `/matches/[id]`, `/profile`, `/account/{billing,data,
sessions}` — dashboard/flow routes are `force-dynamic` ((dash)/layout.tsx:9).

**The API seam (BFF).** `web/src/lib/api/types.ts:102` defines the `Api`
interface, typed to the MCP tool shapes *before the parity API existed*.
`web/src/lib/api/index.ts:32` selects the adapter: `MCPFORWORK_API_URL` set →
`httpApi` (server-side `fetch` forwarding the session cookie, 10 s timeout,
`getMatch` 404 → `null`, `http.ts:13-45`); unset → `fixturesApi` (Sofía Reyes
demo dataset). Fail closed: production without the URL throws unless
`MCPFORWORK_FIXTURES=1` (`index.ts:22`, build phase exempt). Writes go through
public server actions (`web/src/lib/actions.ts`); `updateProfile` re-whitelists
scalar fields (`actions.ts:42-64`). The HTTP path map (`http.ts:47-67`) was the
parity API's build contract — S6.6a/b/c implement it 1:1 (`api/app.py:536-554`).

**ISO across the seam, humanized at render (W6.1).** Every API-owned timestamp
crosses the wire as ISO-8601 (contract on `types.ts:32`); both adapters honor it
(fixtures build relative ISO via `isoAgo`, `fixtures.ts:70-75`). One helper
humanizes: `timeAgo(iso, now?)` (`web/src/lib/time.ts:28`) — <1 min "just now"
(the [45 s, 60 s) window must never render "0 min ago"), <1 h "N min ago", <24 h
"N hr ago", <48 h "Yesterday" (elapsed, not calendar-day), <7 d "N days ago",
else absolute `D Mon` (+year cross-year); unparseable input passes through
unchanged (never crash a render). Render points: `PipelineTable.tsx:183`,
`matches/[id]/page.tsx:53,82`, `account/sessions/page.tsx:34`, `data/page.tsx:40`.

**Sentinels, honest self-host states, billing funnel (W6.1).** `TopBar.tsx:22`
maps the never-synced sentinel `syncedMinAgo < 0` to "Never synced". Billing
branches on `price === "self-host"` (`billing/page.tsx:19`): self-host renders a
$0 "free forever" card, never the hosted $5 pitch. Export is truthful per mode:
`requestExport(): Promise<string>` returns the export inline — self-host has no
mailer, so "we'll email a link" would be a lie — and `DataActions.tsx:18-29`
downloads it as a Blob; `DeleteAccount` (`DataActions.tsx:49-65`) states deletion
is immediate on self-host. Hosted checkout: `createBillingSession` → `isSafeBillingUrl`
guard (https + Stripe host allowlist, `safeRedirect.ts:9`); `url: null` → honest "not wired up" note.

**Docs (W2.1 + W2.2).** Route-per-page under a shared `DocsShell` + `_nav.ts`: the
`DocSlug` literal union (`_nav.ts:11`) makes a slug typo a compile error; `DOCS_ORDER`
(available items only) drives prev/next and the sitemap. W2.2 shipped the last 7 pages
— Reference: `mcp-tools`, `slash-commands`, `configuration`, `digest-email`;
Self-hosting: `install`, `data-backups`, `contribute-a-pack` — no `available: false`
("coming soon") remains. `mcp-tools` reconciles the badge 14 → the real 38-`@mcp.tool()`
count in `server.py`, grouped 10 Profile / 6 Hunt / 5 Review / 5 Generation /
9 Apply / 3 Privacy-meta; `import_from_url_findings` sits under Profile with its real
semantics (applies fields the *client* LLM extracted — the server never fetches the URL).
`slash-commands` documents the 4 real `@mcp.prompt()`s (setup/hunt/review/apply,
`server.py:613-692`) — the specced `/interview` and `/upskill` don't exist. `digest-email`
is honest: the digest is hosted-track; self-host has only `ConsoleMailer` (magic link
to stderr, `adapters/mailer.py:14`), no scheduler. FAQ: `web/src/content/faq.ts`.

**Legal/SEO.** Legal pages share `LegalShell`, carry a "Draft — reviewed by
counsel" banner, and take a static `Last updated` string. SEO uses only Next
built-ins: `site.ts`, `metadataBase` + OG/Twitter defaults, `opengraph-image.tsx`
(`next/og`), `robots.ts`, public-only `sitemap.ts`, `manifest.ts`.

**No-LLM-deps guard.** `web/scripts/check-no-llm-deps.mjs` fails CI if any banned
SDK appears in `package.json` (name *and* npm-alias spec) or `package-lock.json`;
runs in the CI web job (`ci.yml:75`) and at image build (`web/Dockerfile:18`).

**Containers / compose.** `web/Dockerfile`: node:24-alpine multi-stage,
`npm ci --ignore-scripts`, `output: "standalone"`, non-root runner on :3000.
Compose (S6.8, ADR 0006 — supersedes the W1.2 card text): `web` gets
`MCPFORWORK_API_URL=http://api:8000`, **no** `MCPFORWORK_FIXTURES`
(`docker-compose.yml:92-103`), host port `${WEB_PORT:-2200}`, `depends_on: api`;
topology in `modules/self-host.md`.

**Fixture-backed vs live today.** In compose the dashboard is fully live against
the parity API (`tests/test_compose_stack.py:77`); W6.1 browser-verified it on a
fresh volume (login → pipeline → empty states; export returns 11 per-user tables).
Self-host stubs: `/v1/subscription` → static `"self-host"` (the $0 card) and
`/v1/billing/session` → `{url: None}` (`app.py:503-515`) — Stripe is S7.1.
Fixtures remain the dev default and opt-in public-demo mode.

## Design decisions

- **API-contract-first.** `types.ts` + the W1.1 card's binding S6.x contract
  (fail-closed auth, profile allowlist, 404 → `null`, `postingUrl` validation)
  let the UI ship before the API; S6.6a/b/c implemented the seam with zero rework.
- **One time format at the boundary (W6.1).** ISO-8601 on the wire, humanized at
  render — API stays machine-clean, fixtures exercise the same path; hand-rolled.
- **Truthful copy per deployment mode (W6.1).** Self-host has no mailer, Stripe,
  or hosted plan; the UI says so ($0 card, inline export download, immediate
  deletion) rather than promise hosted-track behavior.
- **Docs never fabricate (W2.2).** The fused gate's first run FAILED with 6 P1 accuracy
  defects: wrong `MCPFORWORK_USER_EMAIL` default (the email keys the self-host tenant's
  users row — a wrong default splits tenant data), wrong API host/port defaults, an
  invented `MCPFORWORK_API_URL` default, wrong HTTP methods for export/delete, web port
  3000 vs the real 2200, `import_from_url_findings` misdescribed. All fixed; second run
  PASS. Lesson: trace every default/route/port claim in docs to code.
- **Document what ships, not what the card specced (W2.2).** Deviations resolve
  toward the code (4 real prompts, not 6; digest = hosted-track), recorded on the card.
- **Fail-closed adapter selection** — a production deploy that loses
  `MCPFORWORK_API_URL` must not silently become the fictional demo (W1.1 re-review).
- **Zero new dependencies** across every web card (charter): route-per-page docs,
  the `DocSlug` union instead of a test harness, `next/og`, stdlib `node:test`.
- **Track boundary:** the web loop cannot edit `ci.yml`; the CI test step was
  carded separately (W5.2) and merged inside S6.3. ADRs: 0002, 0003, 0006 (topology, amends 0003).

## Testing

- `npm run test` = `node --test` (zero deps), in CI since W5.2/S6.3 (`ci.yml:83-85`); 10 tests pass (W2.2 close):
  - `web/src/lib/time.test.ts` — 9 `timeAgo` tests with injected `now`: boundary
    pins at 50 s/59.999 s ("just now", the W6.1 fix), 60 s/59 min, 24 h/47 h
    "Yesterday", 7 d absolute, cross-year, unparseable passthrough, psycopg `+00:00`.
  - `web/src/lib/safeRedirect.test.ts` — one test, a 23-case adversarial open-redirect matrix.
- Per-card gates: `npm run build` + `tsc --noEmit` + `check:no-llm-deps` +
  browser verification (W6.1 added a compose e2e gate). W2.2: build green with
  all 7 new routes static; browser-verified (200s, zero "coming soon", badge 38).
- Guard mutant probe (W1.1): crafted manifests killed — direct dep, transitive
  lock entry, `@google/genai`, npm-alias `npm:openai@4`; no false positives.
- Python-side: `tests/test_compose_stack.py` asserts compose web points at the
  real API, fixtures off; Python suite untouched by `web/` (W6.1: 395 passed).

## Gotchas

- **Fixtures store lives on `globalThis`** (`fixtures.ts:210-216`): Next bundles
  the module separately into RSC and server-action chunks, so plain module state
  exists twice and action mutations would be invisible to renders.
- **Fixture timestamps are relative to module load** (`isoAgo`) — a long-lived
  dev server drifts stale; the `needsYou` prose is static demo copy (W6.1 P3).
- **`timeAgo` in a client component** (`PipelineTable`) has a theoretical
  ms-scale hydration-mismatch window at boundaries; React self-corrects (W6.1 P3).
- **`/login` prerenders static** with the build-time `usingFixtures` value
  (W1.1 P3, still open — no `force-dynamic` on that page).
- **`http.ts` forwards the whole cookie jar**, not just the named session cookie
  — narrowing recorded as an S6.1 follow-up (`http.ts:17-18`).
- **Truthful outcomes:** `recordOutcome` must not collapse `rejected→no_response`
  / `offer→interview`; the action guards the source stage (W1.1 P1).
- **Entitlement is never inferred from `?checkout=success`** — webhook-driven
  only (routed to S7.1); banner + trial nudge can coexist during webhook lag.
- **Static-surface rules:** no `new Date()`/`Date.now()` in legal/sitemap ("Last updated" is
  passed in); robots.txt is advisory, not access control (W4.1 P3); `global-error.tsx` hardcodes light hex.
- **Docs drift is real (W2.2):** the `_nav.ts` mcp-tools badge (38) duplicates
  the server's `@mcp.tool()` count by hand — a drift-guard test is uncarded.
