# mcpfor.work — 1.0 Web Dashboard: Design & Build Brief

> **Superseded (2026-07-11):** the design phase resolved this brief's §11 open
> questions and produced hi-fi comps. The authoritative copy now travels with
> the design handoff bundle (`design_handoff_mcpforwork_web/DASHBOARD_BRIEF.md`);
> implementation is carded as `backlog/…/W1.1_web_surfaces.md` with ADR
> `backlog/decisions/0002_nextjs_web_surfaces.md`.

> **This file is a self-contained kickoff prompt.** Paste it whole as the first
> message of a fresh Claude Code (or Claude design) session and say
> *"design the 1.0 dashboard"*. It encodes the product invariants, the exact
> scope, and the sequence of deliverables. Source of truth for everything else:
> [`PRODUCT_PLAN.md`](PRODUCT_PLAN.md) and [`../AGENTS.md`](../AGENTS.md) —
> on conflict, they win.
>
> **Status:** design brief for **S6.3** (Sprint 6 — Hosted alpha), not yet
> carded. Rolling-wave carding means S6.3 becomes a real `backlog/` card only
> when Sprint 6 is reached; this brief is its source material until then.

---

## 0. How to use this brief

You are designing and building the **hosted web dashboard** for mcpfor.work.
Work in this order and **get sign-off at each gate** — do not skip to code:

1. **Read** this brief + `PRODUCT_PLAN.md` §Core thesis, §Onboarding intake
   model, §MCP surface, §Hosted architecture. Then **ask the open questions**
   in §11 before designing anything.
2. **Wireframe** (low-fi) the screens in §5. HTML/React prototype or Figma via
   the Figma MCP — your call. Sign-off gate.
3. **Design system + hi-fi** for the three hero screens (Connect, Onboarding,
   Pipeline). Tokens, not pixel-perfection everywhere. Sign-off gate.
4. **ADR first, then build.** A Next.js app is a new framework not named in the
   architecture spec → it requires an ADR in `backlog/decisions/` before code
   (see §9). Then implement per repo conventions.

---

## 1. What you're building (one sentence)

**A thin, calm control panel for the hosted ($5/mo) tier — the handful of things
a chat client is bad at: signing in, connecting the MCP connector, onboarding
through a form, seeing the whole pipeline at a glance, and managing account,
billing, and data.**

That's it. It is a **mirror and a control panel**, not a workspace.

---

## 2. Prime directive — what the dashboard is NOT

These are hard constraints, not preferences. Violating any of them breaks a
product invariant:

- **It is NOT where the AI works.** No drafting resumes/covers, no job search,
  no chat, no "generate" buttons. All intelligence runs in the user's *own*
  Claude / ChatGPT / Codex client via MCP. **Zero server-side LLM calls; zero
  LLM SDKs in the dependency tree** (`openai`, `anthropic`, etc. must not be
  importable — mirror the Python import-linter rule for the JS app).
- **It is NOT required to use the product.** Self-host users have no dashboard
  and full functionality. Nothing you build here may become load-bearing for
  the core product. Open-core parity is an invariant.
- **It is NOT a 1:1 rendering of the ~26 MCP tools as buttons.** The client LLM
  drives those. The dashboard surfaces *state* and owns only the interactions
  chat can't do well (forms, at-a-glance pipeline, billing, account).
- **It never fabricates or implies fabrication.** Honesty (the "facts
  inventory") is a brand value — see §8.
- **It never automates a browser or submits an application.** Autopilot runs in
  the user's browser via the client, governed by consent policy. The dashboard
  at most *displays* policy and audit; it is not a robot.

If a proposed feature would need an LLM call or a browser action to work, it
does not belong in the dashboard.

---

## 3. Who it's for, and the four jobs it does

Hosted-tier job seekers — often anxious, non-technical, mid-search. The dashboard
does exactly four jobs:

1. **Get connected** — magic-link sign-in, then the one-click *"Connect to
   Claude / ChatGPT"* OAuth connector flow that makes hosted onboarding
   zero-install. This is the single most important conversion moment.
2. **Onboard** — the Tier-1 wizard (< 3 minutes) plus progressive Tier-2
   enrichment. Forms are genuinely better here than in chat.
3. **See the whole pipeline at a glance** — matches → review → applications →
   outcomes. The one view chat fundamentally can't render well.
4. **Manage the account** — billing, data (export/delete), sign-in sessions.

---

## 4. Scope — 1.0 in / out

**IN (the hosted-alpha dashboard = S6.3 + S6.4 + the billing surface of S7.1):**

| Surface | Source | Notes |
|---|---|---|
| Magic-link auth (request + verify) | S6.1 | Session cookie; ports existing magic-link patterns |
| Connector setup / "Connect" screen | S6.2 | The OAuth 2.1 connector grant, shown as a guided flow |
| Onboarding wizard (Tier 1 required, Tier 2 progressive) | S6.3 / intake model | < 3 min to finish Tier 1 |
| Profile editor (all tiers + achievements bank + style profile) | S6.3 | Writes via API parity endpoints |
| Pipeline board (matches → review → applications → outcomes) | S6.3 | The hero screen; see §6 |
| Insight strip (`pipeline_stats`; calibration/gap read-only if present) | Insight tools | Read-only summary tiles |
| Billing (Stripe checkout + portal) | S7.1 | Single $5 plan; free-trial/free-tier per §11 open item |
| Data & privacy (GDPR export / delete + audit-log view) | S6.4 | User owns their data (invariant 6) |
| Account sessions (list / revoke magic-link sessions) | S6.1 | Basic security hygiene |

**OUT / DEFERRED (do not build for 1.0; leave a clean seam):**

- **Autopilot policy UI** (`set_autopilot_policy`, L1/L2) — Sprint 7. At most a
  read-only "Autonomy: Supervised" indicator + a disabled "Coming soon" entry.
- **Any generation / drafting / editor UI** — belongs in the client, never here.
- **Any browser-automation control** — that's the client in the user's browser.
- **Landing / marketing page** — separate deliverable (S8.2 companion brief).
- **Teams / multi-seat, advanced analytics, notification center** — YAGNI.

---

## 5. Information architecture (sitemap + per-screen spec)

Keep the shell minimal: a left nav (Pipeline · Profile · Account) + a top bar
(connection status, plan). Pipeline is home.

| Route | Purpose | Reads | Primary actions | Empty state |
|---|---|---|---|---|
| `/login` | Request + verify magic link | — | Send link · verify token | — |
| `/connect` | Guided connector OAuth grant | connection status | Start "Connect" · copy connector URL | "Not connected yet — connect your Claude/ChatGPT to start" |
| `/onboarding` | Tier-1 wizard → optional Tier-2 | `get_profile` | Save & continue · skip-for-now | Fresh-start wizard step 1 |
| `/pipeline` | At-a-glance funnel (home) | `list_matches`, applications, `pipeline_stats` | Approve/discard match · record outcome · open detail | "No matches yet — run `/hunt` in your client" |
| `/matches/[id]` | Review one match + its assets/apps | `get_match`, `get_assets` | Approve · discard · open source posting | — |
| `/profile` | Editor, tabbed: Required · Deep · Achievements · Style | `get_profile` | Edit + save each section | Prefilled from onboarding |
| `/account/billing` | Plan + Stripe portal | subscription status | Start checkout · manage in portal | "Free trial — N days left" (per §11) |
| `/account/data` | GDPR export / delete + audit log | audit log | Request export · delete account (confirm) | — |
| `/account/sessions` | Active sign-in sessions | sessions | Revoke session | — |

**Guided-not-required:** every screen must degrade gracefully when the user
hasn't done the corresponding thing in their client yet — the dashboard reflects
state, it doesn't block on it. Empty states should point back to the client
prompt that fills them (`/hunt`, `/apply`, etc.).

---

## 6. The pipeline screen (the one that matters)

This is the view chat can't give. It renders the server-side **application state
machine** as a legible funnel:

```
new match → approved / discarded
              └─ draft → filling → awaiting_human | awaiting_submit
                          → submitted → verified → tracked        (+ abandoned)
```

Design guidance:
- **Read-mostly.** The heavy lifting (filling, submitting) happens in the
  client's browser. The dashboard shows *where each application is* and offers
  only the low-risk actions: approve/discard a match, record an outcome, open
  the posting, nudge/mark follow-up.
- **Make it a faithful mirror.** It should feel like it's reflecting what the
  LLM is doing right now. For 1.0, **manual refresh or light polling** is fine —
  do NOT build realtime/SSE infrastructure unless a second concrete need appears
  (anti-over-engineering).
- **Legible consent state.** Every application shows whether it was supervised
  (human-submitted) or autopilot, and its audit is one click away. This is a
  trust surface, not a decoration.
- Kanban vs. table: pick one, justify it in the design review. Bias to a compact
  table with status chips on mobile; a board is optional at desktop width.

---

## 7. Data contract (what it reads, and a dependency to flag)

The dashboard talks to **FastAPI** (the same `services/` layer the MCP entrypoint
wraps) over the magic-link session — **not** to the MCP server directly. The MCP
*tools* listed in `PRODUCT_PLAN.md` §MCP surface define the data shapes, but the
API entrypoint needs **parity read/write endpoints** for what the dashboard uses:

- **Reads:** `get_profile`, `list_matches`, `get_match`, `get_assets`,
  `pipeline_stats`, `calibration_report`, `gap_report`, audit log, subscription
  status, sessions.
- **Writes:** profile create/update (all tiers, achievements, style),
  `approve_match` / `discard_match`, `record_outcome`, GDPR export/delete,
  Stripe checkout/portal session creation.

**Flag as a build dependency:** confirm which of these already exist on the
`entrypoints/api/` side vs. need adding. The dashboard design can proceed against
the tool shapes, but the build depends on API parity. Do not have the dashboard
reach into the DB or re-implement any domain logic — it is a thin driver like
every other entrypoint.

---

## 8. Design language

The product is **infrastructure, not hype**, serving people in a high-stakes,
anxious moment. The whole feel should **reduce anxiety through clarity, honest
progress, and calm**.

- **Honesty as a visual value.** The product never fabricates (facts inventory).
  The UI should never imply the AI invents credentials — frame profile
  completeness as *"what your profile proves"*, show gaps plainly, never nag with
  fake-urgency growth-hacks.
- **Consent as a visual value.** Autonomy state is always legible: supervised by
  default, autopilot (when it exists) clearly and soberly flagged. Trust > flash.
- **Calm, fast, keyboard-friendly.** One clean typeface (system stack is fine),
  restrained neutral palette + a single accent, generous whitespace, no
  dashboards-as-cockpit density. Motion is subtle and functional.
- **Light + dark**, both first-class. **WCAG AA** minimum.
- **Responsive**: onboarding and pipeline-read must work on mobile; account/data
  can be desktop-first.

Propose tokens (color, type scale, spacing, radius) as the design-system output —
not a fixed pixel comp of every screen. If brand assets (logo, colors) exist,
use them; if not, propose a restrained direction and ask (see §11).

---

## 9. Tech & process constraints

- **Stack:** Next.js (App Router) + TypeScript, deliberately thin. Server
  components + `fetch` against FastAPI; session via the magic-link cookie. The
  connector OAuth flow (§S6.2) is a *separate* grant for MCP clients — the
  dashboard guides it but the dashboard's own auth is the magic-link session.
- **No LLM anything.** No `openai`/`anthropic`/LLM SDK in `package.json`. Add a
  CI check mirroring the Python import-linter spirit.
- **Anti-over-engineering charter applies verbatim.** No state-management
  library, component kit, or extra dependency without a second concrete use and
  a one-line justification. Prefer server components + native fetch over client
  data-layer machinery. Every dependency is a line on the card.
- **Parity guardrail:** nothing in the dashboard may become required for the
  self-host product to function.
- **ADR REQUIRED BEFORE CODE.** The architecture spec is Python hexagonal; a
  Next.js app is a new framework/layer not named there → per the charter this is
  a simplicity-reviewer P0-block unless there's an ADR in `backlog/decisions/`.
  The ADR must decide, at minimum: **(a)** where the dashboard lives — a
  `apps/dashboard/` folder in this monorepo vs. a separate repo — and **(b)** how
  it authenticates to and calls the API without crossing hexagonal boundaries
  (it's a driving adapter like the others: thin, auth + serialization only).
- **Final-review gate** (test-auditor · code-reviewer · simplicity-reviewer ·
  security-reviewer) applies to the eventual build. Security surfaces to call
  out for this app: session/cookie handling, the connector OAuth redirect,
  Stripe webhook/return handling, RLS/tenant isolation on every read, and the
  destructive GDPR-delete confirmation flow.

---

## 10. Deliverables & sequence (what to produce)

1. **Answers to §11** (ask the user; don't assume).
2. **Low-fi wireframes** for the nine screens in §5, with the empty/loading/error
   states called out. → sign-off.
3. **Design system tokens** + **hi-fi comps for the three hero screens**
   (`/connect`, `/onboarding`, `/pipeline`) in light + dark. → sign-off.
4. **The ADR** (`backlog/decisions/`) for the Next.js layer + placement + auth.
5. **Implementation** per repo conventions, TDD, thin driving-adapter discipline,
   then the four-reviewer final-review gate.

---

## 11. Open questions — resolve BEFORE designing

1. **Free tier vs. trial-only?** (`PRODUCT_PLAN.md` open item — e.g. 25 tracked
   findings free, vs. free-trial-then-pay.) Changes the billing screen and any
   gating/upgrade prompts.
2. **Where does the dashboard code live?** `apps/dashboard/` in this repo, or a
   separate repo? (This is the ADR's first decision — but the user may already
   have a preference.)
3. **Profile writes via the dashboard** — confirmed in scope (onboarding +
   profile editing), so we need API write-parity endpoints. Confirm nothing is
   meant to be MCP-only.
4. **Pipeline freshness** — manual refresh / polling for 1.0 (recommended), or is
   near-realtime a requirement? (Recommend deferring realtime.)
5. **Autopilot in 1.0?** Recommend deferring to Sprint 7 and shipping only a
   read-only "Supervised" indicator. Confirm.
6. **Brand assets** — is there a logo / palette / name treatment, or should the
   design propose one?

---

## 12. Definition of done (1.0)

A hosted user can, with no terminal and no server-side LLM call anywhere in the
path:

- **Sign in** via magic link, and **connect** their Claude/ChatGPT client in one
  guided flow.
- **Complete Tier-1 onboarding in under 3 minutes**, with Tier-2 offered
  progressively.
- **See their whole pipeline** at a glance and take the low-risk actions
  (approve/discard, record outcome), with consent/audit state legible.
- **Edit their profile** (all tiers, achievements, style).
- **Manage billing** (checkout + Stripe portal) and **export or delete their
  data**.
- On **mobile**, at least sign-in, onboarding, and pipeline-read work.
- The app ships with a check proving **no LLM SDK** is in its dependency tree,
  and **nothing here is required** for the self-host product to function.
