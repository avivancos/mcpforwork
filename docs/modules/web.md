# Web surfaces (Next.js dashboard + public site)

> The `web/` app: marketing landing, docs site, legal/SEO pages, and the
> hosted dashboard 1.0 — a **mirror and control panel, never a workspace**
> (ADR 0002). Built API-contract-first against a typed seam, shipped on
> fixtures, now wired to the real parity API in compose. Cards (latest
> first): S6.3, W5.2, W5.1, W4.1, W3.1, W2.1, W1.2, W1.1.

## How it works

**Stack.** Next.js 15 App Router + TypeScript, server components + native
`fetch`, plain CSS modules with custom-property tokens. No state library, no
component kit, no Tailwind; runtime deps are exactly `next`/`react`/
`react-dom` (`web/package.json:15`). Dark mode is scoped to the dashboard via
`[data-allow-dark]` (`web/src/app/(app)/layout.tsx:8`); landing/docs/legal
are light-only by design.

**Routes.** Public: `/`, `/pricing`, `/faq`, `/docs` + 9 doc pages,
`/privacy`, `/terms`, `/security`. App group: `(flow)` = `/login`,
`/connect`, `/onboarding`; `(dash)` = `/pipeline`, `/matches/[id]`,
`/profile`, `/account/{billing,data,sessions}`. Dashboard/flow routes are
`force-dynamic` (`web/src/app/(app)/(dash)/layout.tsx:9`).

**The API seam (BFF).** `web/src/lib/api/types.ts:102` defines the `Api`
interface — typed to the MCP tool shapes *before the parity API existed*.
`web/src/lib/api/index.ts:32` selects the adapter per process:
`MCPFORWORK_API_URL` set → `httpApi` (BFF: server-side `fetch` forwarding the
session cookie, 10 s timeout, no retries, trailing-slash strip, `getMatch`
404 → `null`, `web/src/lib/api/http.ts:13-45`); unset → `fixturesApi`
(Sofía Reyes demo dataset, in-memory mutations). Fail closed: production
without `MCPFORWORK_API_URL` throws unless `MCPFORWORK_FIXTURES=1`
(`index.ts:22`); the build phase is exempt (`index.ts:20`). Writes go through
public server actions (`web/src/lib/actions.ts`) that revalidate affected
routes; `updateProfile` re-whitelists scalar fields server-side
(`actions.ts:42-64`). The HTTP path map (`http.ts:47-67`) was the contract
the parity API was later built against — S6.6a/b/c implement it 1:1
(`src/mcpforwork/entrypoints/api/app.py:536-554`).

**Docs/legal/SEO.** Route-per-page docs with a shared `DocsShell` and
`_nav.ts` config: the `DocSlug` literal union (`web/src/app/docs/_nav.ts:11`)
makes a slug typo a compile error; `DOCS_ORDER` (`_nav.ts:81`) drives
prev/next and the sitemap. FAQ content is a single shared module
(`web/src/content/faq.ts`) consumed by both the landing and `/faq`. Legal
pages share `LegalShell`, carry a "Draft — reviewed by counsel" banner, and
take a static `Last updated` string (reproducible builds). SEO infra uses
only Next built-ins: `SITE_URL`/`SITE_TITLE` in `web/src/lib/site.ts:5`,
`metadataBase` + OG/Twitter defaults, `app/icon.svg`, `opengraph-image.tsx`
via `next/og`, `robots.ts` (disallows private prefixes, `robots.ts:11`),
public-only `sitemap.ts:6`, `manifest.ts`, branded `not-found.tsx` +
`global-error.tsx`.

**Billing funnel.** `/account/billing` → `createBillingSession('checkout' |
'portal')` → `isSafeBillingUrl` guard (https + Stripe host allowlist,
`web/src/lib/safeRedirect.ts:9`) → `window.location.assign`. `url: null`
degrades to an honest "billing isn't wired up" note; `?checkout=success|
canceled` return states render on the billing page.

**No-LLM-deps guard.** `web/scripts/check-no-llm-deps.mjs` fails CI if any
banned SDK appears in `package.json` (name *and* npm-alias spec, `:42`) or
anywhere in `package-lock.json` (required, `:51`; matches install path and
resolved `name`). Runs in the CI web job (`.github/workflows/ci.yml:75`) and
at image build time (`web/Dockerfile:18`).

**Containers / compose.** `web/Dockerfile`: node:24-alpine multi-stage,
`npm ci --ignore-scripts`, `output: "standalone"` (`web/next.config.ts:6`),
non-root runner on :3000. **Current `docker-compose.yml` (S6.8, ADR 0006 —
supersedes the W1.2 card text):** three services; `web` gets
`MCPFORWORK_API_URL=http://api:8000` with **no** `MCPFORWORK_FIXTURES`
(`docker-compose.yml:92-103`), host port `${WEB_PORT:-2200}`, `depends_on:
api`. The W1.2-era state (fixtures on, API URL commented out) no longer
exists on disk. Full topology: see `modules/self-host.md`.

**Fixture-backed vs live today.** In compose the dashboard is fully live
against the parity API (asserted by `tests/test_compose_stack.py:77`). Still
stubbed server-side on self-host: `/v1/subscription` returns a static
"self-host" payload and `/v1/billing/session` returns `{url: None}`
(`app.py:503-515`) — Stripe is S7.1 (deferred, hosted scope), so the billing
page shows the same honest-degrade note as fixtures. Fixtures remain the dev
default and the opt-in public-demo mode.

## Design decisions

- **API-contract-first.** `types.ts` + the W1.1 card's binding S6.x contract
  (fail-closed auth, profile allowlist, 404 → `null`, `postingUrl` scheme
  validation) let the UI ship months before the API; S6.6a/b/c then
  implemented to the seam with zero UI rework.
- **Fail-closed adapter selection** — a production deploy that loses
  `MCPFORWORK_API_URL` must not silently become the fictional demo behind a
  real login (W1.1 re-review).
- **Zero new dependencies** across W2–W5 (charter): route-per-page docs, the
  `DocSlug` union instead of a test harness, `next/og`, stdlib `node:test`.
- **Track boundary:** the web loop is forbidden from editing `ci.yml`, so the
  CI test step was carded separately (W5.2) and executed inside the S6.3
  merge — the sanctioned disposition for cross-boundary enforcement.
- ADRs: 0002 (Next.js surfaces), 0003 (compose), 0006 (full-stack topology,
  amends 0003).

## Testing

- No JS unit harness for the app (charter-appropriate): per-card gates are
  `npm run build` + `tsc --noEmit` + `check:no-llm-deps` + browser
  verification (desktop, 390px, dark).
- The one unit suite: `web/src/lib/safeRedirect.test.ts` — 23-case
  adversarial `node:test` matrix for the open-redirect guard; `npm run test`
  = `node --test` (type-stripping), wired into CI by W5.2/S6.3
  (`ci.yml:83-85`).
- Guard mutant probe (W1.1, AGENTS.md §4 substitute): crafted manifests
  killed — direct dep, transitive lock entry, `@google/genai`, npm-alias
  `npm:openai@4`; no false positives on bare `ai`/`chai`.
- Python-side: `tests/test_compose_stack.py` asserts the compose web service
  points at the real API with no fixtures flag. The Python suite is
  untouched by `web/` (additive).

## Gotchas

- **Fixtures store lives on `globalThis`** (`fixtures.ts:210-216`): Next
  bundles the module separately into RSC and server-action chunks, so plain
  module state exists twice and action mutations are invisible to renders.
- **`/login` prerenders static** with the build-time `usingFixtures` value
  (W1.1 P3, still open — no `force-dynamic` on that page).
- **`http.ts` forwards the whole cookie jar**, not just the named session
  cookie — narrowing was recorded as an S6.1 follow-up and the code comment
  (`http.ts:17-18`) is still current.
- **Truthful outcomes:** `recordOutcome` must not collapse
  `rejected→no_response` / `offer→interview`; `Stage` includes
  `offer`/`rejected` and the action guards the source stage (W1.1 P1).
- **Entitlement is never inferred from `?checkout=success`** — webhook-driven
  only (routed to S7.1); success banner + trial nudge can coexist during
  webhook lag.
- **Reproducible builds:** no `new Date()`/`Date.now()` in legal/sitemap —
  "Last updated" is a passed-in static string.
- **robots.txt is advisory, not access control** (W4.1 P3); `(app)` route
  confidentiality depends on server-side auth. `global-error.tsx` hardcodes
  light-theme hex because it replaces the root layout.
- **Compose drift vs W1.2:** the card describes fixtures-on + commented
  `MCPFORWORK_API_URL`; on disk today (S6.8) the web service is live-wired
  and the host port is 2200, not 3000.
