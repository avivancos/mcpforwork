# Web surfaces (Next.js dashboard + public site)

> The `web/` app: marketing landing, docs site, legal/SEO pages, and the
> dashboard — a **mirror and control panel, never a workspace** (ADR 0002).
> Built API-contract-first on a typed seam, shipped on fixtures, live against
> the real parity API in compose since W6.1. Cards (latest first): W6.1, S6.3,
> W5.2, W5.1, W4.1, W3.1, W2.1, W1.2, W1.1.

## How it works

**Stack.** Next.js 15 App Router + TypeScript, server components + native
`fetch`, plain CSS modules with custom-property tokens. No state library, no
component kit, no Tailwind; runtime deps are exactly `next`/`react`/`react-dom`
(`web/package.json:15`). Dark mode is dashboard-scoped (`[data-allow-dark]`);
landing/docs/legal are light-only by design.

**Routes.** Public: `/`, `/pricing`, `/faq`, `/docs` + 9 doc pages, `/privacy`,
`/terms`, `/security`. App group: `(flow)` = `/login`, `/connect`, `/onboarding`;
`(dash)` = `/pipeline`, `/matches/[id]`, `/profile`, `/account/{billing,data,
sessions}` — dashboard/flow routes are `force-dynamic` ((dash)/layout.tsx:9).

**The API seam (BFF).** `web/src/lib/api/types.ts:102` defines the `Api`
interface, typed to the MCP tool shapes *before the parity API existed*.
`web/src/lib/api/index.ts:32` selects the adapter: `MCPFORWORK_API_URL` set →
`httpApi` (server-side `fetch` forwarding the session cookie, 10 s timeout,
`getMatch` 404 → `null`, `web/src/lib/api/http.ts:13-45`); unset → `fixturesApi`
(Sofía Reyes demo dataset). Fail closed: production without the URL throws unless
`MCPFORWORK_FIXTURES=1` (`index.ts:22`); the build phase is exempt. Writes go
through public server actions (`web/src/lib/actions.ts`) that revalidate affected
routes; `updateProfile` re-whitelists scalar fields server-side (`actions.ts:42-64`).
The HTTP path map (`http.ts:47-67`) was the contract the parity API was built
against — S6.6a/b/c implement it 1:1 (`entrypoints/api/app.py:536-554`).

**ISO across the seam, humanized at render (W6.1).** Every API-owned timestamp
crosses the wire as ISO-8601 (contract documented on `types.ts:32`); both
adapters honor it — fixtures build relative ISO via `isoAgo` at module load
(`fixtures.ts:70-75`). One helper humanizes: `timeAgo(iso, now?)`
(`web/src/lib/time.ts:28`) — <1 min "just now" (the whole first minute; the
[45 s, 60 s) window must never render "0 min ago"), <1 h "N min ago", <24 h
"N hr ago", <48 h "Yesterday" (elapsed time, not calendar-day), <7 d "N days ago",
else absolute `D Mon` with the year only cross-year. Unparseable input passes
through unchanged (a render must never crash on a bad timestamp); psycopg's
`+00:00` timestamptz shape parses. Render points: `PipelineTable.tsx:183`,
`matches/[id]/page.tsx:53,82` (updated + audit `at`), `account/sessions/page.tsx:34`
(`lastSeen`), `account/data/page.tsx:40` (audit `at` + honest empty-audit state).

**Sentinels, honest self-host states, billing funnel (W6.1).** `TopBar.tsx:22`
maps the never-synced sentinel `syncedMinAgo < 0` to "Never synced". Billing page
and sidebar trial line branch on `price === "self-host"` (`billing/page.tsx:19`,
`(dash)/layout.tsx:30`): self-host renders a $0 "free forever" card, never the
hosted $5 pitch. Export is truthful per mode: `requestExport(): Promise<string>`
(`types.ts:121-122`) returns the export inline — self-host has no mailer, so
"we'll email a link" would be a lie — and `DataActions.tsx:18-29` downloads it as
a Blob file. `DeleteAccount` (`DataActions.tsx:49-65`) states deletion is immediate
on self-host and promises a confirmation email only in fixtures preview. Hosted
checkout: `createBillingSession` → `isSafeBillingUrl` guard (https + Stripe host
allowlist, `web/src/lib/safeRedirect.ts:9`) → `window.location.assign`; `url: null`
degrades to an honest "not wired up" note; `?checkout=success|canceled` renders.

**Docs/legal/SEO.** Route-per-page docs with a shared `DocsShell` and `_nav.ts`:
the `DocSlug` literal union (`web/src/app/docs/_nav.ts:11`) makes a slug typo a
compile error; `DOCS_ORDER` drives prev/next and the sitemap. FAQ is one shared
module (`web/src/content/faq.ts`). Legal pages share `LegalShell`, carry a
"Draft — reviewed by counsel" banner, and take a static `Last updated` string.
SEO uses only Next built-ins: `site.ts`, `metadataBase` + OG/Twitter defaults,
`opengraph-image.tsx` (`next/og`), `robots.ts`, public-only `sitemap.ts`, `manifest.ts`.

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
the parity API (asserted by `tests/test_compose_stack.py:77`); W6.1 browser-verified
it on a fresh volume: magic-link redeem from `docker compose logs api` → 302 to
:2200/pipeline → honest empty states on pipeline, billing, sessions, data; export
returns all 11 per-user tables. Self-host stubs: `/v1/subscription` returns static
`"self-host"` (→ the $0 card) and `/v1/billing/session` returns `{url: None}`
(`app.py:503-515`) — Stripe is S7.1 (hosted scope). Fixtures remain the dev default
and opt-in public-demo mode (hosted $5 pitch + `url: null` degrade).

## Design decisions

- **API-contract-first.** `types.ts` + the W1.1 card's binding S6.x contract
  (fail-closed auth, profile allowlist, 404 → `null`, `postingUrl` validation)
  let the UI ship months before the API; S6.6a/b/c implemented to the seam with
  zero UI rework; W6.1's audit found only two drift points (export/delete copy,
  self-host price).
- **One time format at the boundary (W6.1).** ISO-8601 across the wire, humanized
  at render: every surface speaks one format, the API stays machine-clean, fixtures
  exercise the same code path. Hand-rolled — no date library for one function.
- **Truthful copy per deployment mode (W6.1).** Self-host has no mailer, Stripe,
  or hosted plan; the UI must say so ($0 card, inline export download, immediate
  deletion) rather than promise hosted-track behavior.
- **Fail-closed adapter selection** — a production deploy that loses
  `MCPFORWORK_API_URL` must not silently become the fictional demo behind a real
  login (W1.1 re-review).
- **Zero new dependencies** across W1–W6 (charter): route-per-page docs, the
  `DocSlug` union instead of a test harness, `next/og`, stdlib `node:test`.
- **Track boundary:** the web loop cannot edit `ci.yml`, so the CI test step was
  carded separately (W5.2) and executed inside the S6.3 merge. ADRs: 0002 (Next.js
  surfaces), 0003 (compose), 0006 (full-stack topology, amends 0003).

## Testing

- `npm run test` = `node --test` (type-stripping, zero deps), in CI since
  W5.2/S6.3 (`ci.yml:83-85`); 10 tests pass (verified at W6.1 close):
  - `web/src/lib/time.test.ts` — 9 `timeAgo` tests with injected `now`: boundary
    pins at 50 s/59.999 s ("just now", the W6.1 review fix), 60 s/59 min, 24 h/47 h
    "Yesterday", 7 d absolute, cross-year suffix, unparseable passthrough, clock
    skew, psycopg `+00:00` shape.
  - `web/src/lib/safeRedirect.test.ts` — one test driving a 23-case adversarial
    matrix for the open-redirect guard.
- Other per-card gates: `npm run build` + `tsc --noEmit` + `check:no-llm-deps` +
  browser verification (desktop, 390px, dark); W6.1 added a compose end-to-end
  demo gate (fresh volume, real login, empty states).
- Guard mutant probe (W1.1): crafted manifests killed — direct dep, transitive
  lock entry, `@google/genai`, npm-alias `npm:openai@4`; no false positives.
- Python-side: `tests/test_compose_stack.py` asserts compose web points at the real
  API, fixtures off; Python suite untouched by `web/` (W6.1: 395 passed).

## Gotchas

- **Fixtures store lives on `globalThis`** (`fixtures.ts:210-216`): Next bundles
  the module separately into RSC and server-action chunks, so plain module state
  exists twice and action mutations would be invisible to renders.
- **Fixture timestamps are relative to module load** (`isoAgo`) — a long-lived dev
  server drifts stale until restart. The `needsYou` fixture prose is static
  pre-humanized demo copy, not seam data (W6.1 P3, accepted).
- **`timeAgo` in a client component** (`PipelineTable`) has a theoretical ms-scale
  hydration-mismatch window at boundaries; React self-corrects — watch (W6.1 P3).
- **`/login` prerenders static** with the build-time `usingFixtures` value
  (W1.1 P3, still open — no `force-dynamic` on that page).
- **`http.ts` forwards the whole cookie jar**, not just the named session cookie —
  narrowing recorded as an S6.1 follow-up (`http.ts:17-18`).
- **Truthful outcomes:** `recordOutcome` must not collapse `rejected→no_response` /
  `offer→interview`; `Stage` includes both and the action guards the source stage
  (W1.1 P1).
- **Entitlement is never inferred from `?checkout=success`** — webhook-driven only
  (routed to S7.1); success banner + trial nudge can coexist during webhook lag.
- **Reproducible builds:** no `new Date()`/`Date.now()` in legal/sitemap —
  "Last updated" is a passed-in static string.
- **robots.txt is advisory, not access control** (W4.1 P3); `(app)` confidentiality
  depends on server-side auth. `global-error.tsx` hardcodes light-theme hex
  (replaces the root layout).
