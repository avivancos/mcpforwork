# ADR 0002 — Next.js web layer: placement and adapter discipline

**Status:** Accepted · 2026-07-11
**Card:** `backlog/in_progress/W1.1_web_surfaces.md`

## Context

`PRODUCT_PLAN.md` §Hosted architecture names a "thin Next.js dashboard", but
§Architecture spec defines only the Python hexagonal layout, and the
anti-over-engineering charter P0-blocks any framework/layer not named there
without an ADR. The user directed a pull-forward of the web surfaces (landing,
docs shell, dashboard 1.0) from the Claude Design handoff, with Next.js (App
Router + TypeScript) as the resolved stack choice.

Two questions must be settled before code (brief §9): **(a)** where the app
lives, and **(b)** how it authenticates to and calls the backend without
crossing hexagonal boundaries.

## Decision

### (a) Placement: this monorepo, top-level `web/`

One Next.js app serves all three surfaces — landing at `/`, docs at `/docs`,
dashboard routes per brief §5. Host mapping (`mcpfor.work`,
`docs.mcpfor.work`, app subdomain) is a deploy concern, not a code concern.

- Solo + agents team: one repo means shared design tokens, atomic cards, one
  review gate, no cross-repo version drift.
- A separate repo is the "second concrete use" kind of split — justified only
  when an independent release cadence or team actually exists (rule of two).
- `web/` sits OUTSIDE `src/mcpforwork/` — it is not a Python package and must
  never be importable from one. Conceptually it is a **driving adapter**
  (like `entrypoints/*`), physically it is a sibling toolchain.
- Not three apps: landing and docs are static pages inside the same app;
  splitting builds/deploys for them now is YAGNI.

### (b) Backend access: one typed seam, cookie session, fixtures until parity

- The web app talks **only** to the FastAPI parity endpoints (brief §7) — it
  never touches the DB, never imports domain logic, never re-implements
  scoring/dedup/consent. Thin driver: auth + serialization only.
- Single seam: `web/src/lib/api/` exposes typed functions shaped by the MCP
  tool contracts (`get_profile`, `list_matches`, `pipeline_stats`, …). Two
  interchangeable adapters behind one interface:
  - **HTTP adapter** (when `MCPFORWORK_API_URL` is set): server-side `fetch`
    with the magic-link session cookie forwarded; no client-side tokens.
  - **Fixtures adapter** (default until S6.x lands): in-memory Sofía Reyes
    dataset. Lets the UI ship, demo, and be reviewed today without faking a
    backend elsewhere in the code.
- The connector OAuth flow (S6.2) is a *separate* grant for MCP clients; the
  dashboard only links to it. Dashboard auth = magic-link session (S6.1).
- Freshness: manual refresh + light polling ("Synced N min ago"). No
  SSE/websockets until a second concrete need exists.

## Invariants made structural

- **Zero LLM SDKs in the web dependency tree** — `web/scripts/check-no-llm-deps.mjs`
  fails CI if `openai`/`anthropic`/`@anthropic-ai/*`/`ai` etc. appear anywhere
  in the dependency graph (the import-linter rule, mirrored for JS).
- **Non-load-bearing:** `web/` is additive; the Python suite and self-host
  path do not reference it. Nothing in the core may import from or depend on
  the dashboard.
- **Dependency budget:** runtime deps are exactly `next`, `react`,
  `react-dom`. No state library, no component kit, no CSS framework — plain
  CSS custom properties carry the handoff token sheet. Any addition needs a
  justification line on its card.

## Alternatives rejected

- **Separate repo** — coordination cost with zero current benefit.
- **Astro / static HTML** — user resolved Next.js; the dashboard needs forms,
  server actions, and a session, which the static options would bolt on.
- **Tailwind / shadcn / Radix** — the comps are bespoke and complete; a kit
  adds a dependency tree to restyle, violating the charter for no gain.

## Consequences

- Node toolchain joins CI as an isolated job (build + `tsc --noEmit` + LLM-SDK
  guard); Python jobs are untouched.
- All brief §7 endpoints are **flagged gaps** (no `entrypoints/api/` exists);
  they become S6.x cards. Swapping fixtures → HTTP is a one-file change at the
  seam, no UI edits.
- Autopilot UI, kanban board, realtime, teams remain out of scope (deferred
  per the resolved decisions).
