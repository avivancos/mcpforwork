# mcpfor.work — 10/10 MCP Product Spec & Clean-Architecture Plan

> **This file is a self-contained bootstrap for a FRESH session.** Paste it whole (or attach it) as the first message of a new Claude Code session. No prior context is needed. Kickoff instructions below.

## How to run this plan in a fresh session (kickoff)

Paste this plan and say "bootstrap it". The session should then:

1. **Create the repo:** `~/Desarrollo/mcpforwork` — `git init`, branch `main`, Apache-2.0 LICENSE, English-only.
2. **Install the tweaked harness** from the local template at `~/Desarrollo/agents-specs` (see §Development harness below): 4 reviewer sub-agents + final-review gate + backlog kit, copied INTO the new repo (never keep a project's backlog inside agents-specs). Fill template placeholders: `<RUN_ENV>`=uv+docker, `<DOC_LANGUAGE>`=English, `<DEFAULT_BRANCH>`=main.
3. **Author `AGENTS.md` + `CLAUDE.md`** — the template points to an `AGENTS.md` source-of-truth that does NOT exist in the template; write it fresh from this plan's invariants (core thesis §1–6, anti-over-engineering charter, TDD + no-mocks testing rules, explicit-path commits).
4. **Scaffold the skeleton** per §Architecture spec: `pyproject.toml` (uv + hatchling), `src/mcpforwork/{domain,services,ports,adapters,entrypoints,packs}`, pytest no-mocks harness, ruff, import-linter boundary contracts, CI (lint + tests + contracts).
5. **Card Sprint 0 + Sprint 1** into `backlog/pending/` (rolling wave — see §Sprint plan; one card per S-item, named `S0.1_repo_bootstrap.md` etc.), then start S0.1.

**Binding working rules for every card:** spec → red → green → refactor → doc; commits with explicit paths (never `git add -A`); a card moves to `done/` only after the **final-review gate** (all 4 reviewers PASS); the anti-over-engineering charter can P0-block.

## Context

Pivot of startup-jobs-radar (Coverpilot) into **mcpfor.work**: an open-source, MCP-first job-search copilot for **any sector, any country**, with a hosted version at **$5/mo flat**. Everything English-first from now on. The product combines our proven infrastructure (dedup engine, dual-backend DB, multi-tenant RLS, supervised-apply invariant, 508 passing tests) with the best ideas from `MadsLorentzen/ai-job-search` (deep personalization, honesty rules, outcome calibration, interview prep) — delivered through an architecture where **we never operate LLM tokens**.

## Core thesis (product invariants)

1. **The LLM is the client.** All intelligence (searching via browser, drafting resumes/covers, evaluating fit narratively) runs inside the user's own Claude or ChatGPT/Codex subscription, connected to our MCP server. We never make server-side LLM calls. Zero token opex → $5/mo is sustainable and honest.
2. **Graduated autonomy, consent-based.** Default is supervised (human reviews and submits). With explicit opt-in, **Autopilot Apply** lets Claude-in-Chrome complete and submit applications in the USER'S OWN browser session, governed by a user-set policy: score threshold, daily cap, source allowlist (`auto_apply_safe` sites only), always interruptible, every action audited. No dark autonomy: there is never a server-side robot — automation only runs in the user's browser with their session. (Evolves today's §2 invariant from "never submit" to "never submit without recorded consent + policy".)
3. **Open-core.** Full product self-hostable for free (SQLite, local, no account). Hosted = convenience: nothing to install, remote MCP with one-click connector OAuth, web dashboard, sync, backups. One plan: $5/mo.
4. **Never fabricate.** Generation briefs include a "facts inventory" — the client LLM may only claim what the profile proves. Gaps are acknowledged, never stuffed (ai-job-search honesty rule, made structural).
5. **Sector- and country-agnostic by data, not code.** Source packs and sector packs are versioned data files, community-contributable, updatable independently of releases.
6. **User owns their data.** Export/delete (GDPR patterns already built), EEO data optional and privacy-gated.

## "Claude OAuth / Codex OAuth — is it possible?" — Answered

- **We do NOT need OAuth into Anthropic or OpenAI.** Neither vendor lets third-party servers spend a user's subscription server-side. We don't need it: in MCP architecture the user's client (Claude.ai, Claude Desktop, Claude Code, ChatGPT desktop, Codex CLI) IS the LLM, already paid by the user.
- **The OAuth we DO implement:** MCP remote-connector authorization (OAuth 2.1 + PKCE + dynamic client registration, per the MCP spec). We are the authorization server; the user clicks "Connect" in Claude/ChatGPT and grants access to their mcpfor.work account. This is what makes hosted onboarding zero-install.
- **Codex/ChatGPT side:** ChatGPT supports remote MCP connectors on paid plans; Codex CLI supports MCP servers (stdio + remote). Same server, both ecosystems.
- **Consequence:** the $5 gate is infrastructure (storage, dedup, packs, dashboard, sync), not LLM resale. Self-host users pay nothing and bring their own client the same way.

## Repo decision: NEW repo, with organ transplants

**Verdict: start a fresh English-first repo** (working name: `mcpforwork`) with a clean spec, and port proven modules WITH their tests. This sheds architectural debt (Spanish CLI, stale :8787 dashboard, tech-hardcoded scoring, server-side LLM generation, port fragmentation, unused heavy deps) without rewriting hard-won correctness.

**Port (with tests) from startup-jobs-radar:**
| Module | Why |
|---|---|
| `urls.py` canonical_url + `services/dedup.py` + external_applications schema | Card-11 bulletproof dedup — hardest-won correctness in the repo |
| `backend.py` dual SQLite/Postgres + migrations pattern + RLS/multitenancy lessons (C1, pre-auth RLS, FK-safe recreation) | Years of landmines already stepped on |
| ATS adapters + `ats_form_maps` + fill_plan supervised-steps design | Powers guided form-fill |
| `sources.yaml` content → restructured into packs | 155 curated sources as seed data |
| Magic-link auth, session util, billing webhook patterns (card 9), usage caps pattern (card 26) | Hosted plumbing, already adversarially reviewed |
| Onboarding regex CV parser (zero-LLM default) | §1 zero-cost invariant |
| No-mocks test discipline + conftest patterns | Quality bar |

**Leave behind:** Jinja dashboard, `headroom-ai`, server-side OpenAI/Anthropic generation in `ai/generate.py` (replaced by client-LLM briefs), hardcoded `match/keywords.py` scoring, Spanish CLI text, Playwright remnants. Current repo stays as read-only reference.

## Architecture spec: pragmatic Hexagonal (Ports & Adapters) over a modular monolith

**Decision: Hexagonal architecture, pragmatic variant — NOT full Clean Architecture ceremony.** The current repo already converged on this empirically (card-7: MCP tools as thin wrappers over `services/`; `backend.py` as a dual-adapter DB port); the new repo makes it explicit from day one.

**Why it fits:** one domain, many drivers (MCP stdio, MCP streamable-HTTP, REST, CLI — all thin); swappable driven sides that ARE the open-core split (SQLite↔Postgres/RLS, Stripe on/off, mailer on/off, FS↔object storage); invariants become structural (zero-LLM = no LLM SDK importable from core, enforced by import-linter; consent gate = submit steps only constructible inside the application service; dedup/caps in the domain so no entrypoint can bypass them — the card-9 lesson solved by construction).

**Repo layout:**

```
src/mcpforwork/
  domain/        # PURE logic, no I/O: canonical_url+dedup, scoring, pack schema,
                 # apply state machine, generation briefs, facts inventory
  services/      # use cases (application layer): (uow, user_id, ...) explicit,
                 # caller commits; consent + caps + dedup gates live here
  ports/         # typing.Protocol seams: Database/UoW, Mailer, Billing, FileStore, Clock
  adapters/      # driven: db/{sqlite,postgres,migrations}, billing/stripe,
                 # mail/brevo, files/
  entrypoints/   # driving, all thin (auth + serialization only):
                 # mcp/ (FastMCP), api/ (FastAPI), cli/ (Typer)
  packs/         # DATA not code: country/sector source packs + schema validator
```

**Deliberately skipped (ceremony that would slow a solo+agents team):** interface-for-every-class, entity↔DTO mapping layers, DI frameworks (Python Protocols + explicit args suffice), ORM/repository-per-aggregate (the battle-tested raw-SQL dual-dialect layer IS the persistence adapter), microservices.

**Boundary enforcement in CI:** import-linter contracts (domain imports nothing from adapters/entrypoints; entrypoints never import each other; no `openai`/`anthropic` importable from domain/services), plus grep-gates for consent verbs — architecture drift fails the build, not a review comment.

## Onboarding intake model

**Design rule: required tier completable in under 3 minutes; everything else is progressive** (asked contextually when it becomes useful, e.g. "this posting asks about notice period — add yours?").

### Tier 1 — Required (blocks nothing else; wizard step 1-2)
| Field | Why it's required |
|---|---|
| Name + email | Identity on every asset and application |
| Country + city | Market selection (which source packs), legal context |
| Work authorization (countries authorized; needs visa sponsorship y/n) | #1 hard filter on both sides |
| Target job titles (1–5) + sector(s) | Drives source-pack + keyword seeding — replaces today's hardcoded tech persona |
| Seniority (entry/mid/senior/lead/exec) | Filtering + tone of materials |
| Employment type (full-time / contract / part-time / freelance) | Different markets entirely |
| Work mode (remote/hybrid/onsite) + relocation willingness | Hard filter |
| Minimum salary + currency + period (private) | Deal-breaker filter; never disclosed in materials without consent |
| Languages + proficiency | Filters postings and sets asset language |
| CV: paste text, upload, or LinkedIn URL (guided import — the client LLM reads the public profile and submits structured data) | Seeds the whole profile |

### Tier 2 — Deep personalization (progressive; each unlock improves output measurably)
| Field | What it unlocks |
|---|---|
| LinkedIn / GitHub / portfolio / personal site URLs | Profile enrichment (ai-job-search `/expand` idea: client LLM scans them and proposes additions with source tags) |
| Availability date / notice period | Form answers, recruiter replies |
| **Achievements bank** (quantified wins: metric + context + role) | Resume bullets and cover letters that aren't generic — the single highest-leverage input |
| **Writing sample** (an email/letter they wrote) | Style profile so drafts sound like THEM, not like AI |
| Deal-breakers (max travel %, on-call, industries to avoid, company sizes) | Veto filters + honest fit scoring |
| Career narrative (what they want more of / less of next) | Cover-letter framing, fit evaluation |
| STAR stories bank | `/interview` prep |
| Past applications + outcomes | Calibration loop (what actually got interviews) |
| Salary expectation (public version) + negotiation floor | Offer-stage guidance |
| EEO/demographics | Optional, encrypted-at-rest, only used to pre-fill voluntary sections, never in scoring |

## Personalization engine (resumes & cover letters)

Client-LLM generation with server-side determinism where it counts:

1. **`get_generation_brief(job_id, asset_type)`** returns a structured brief: extracted job requirements, keyword map, the **facts inventory** (only claims the profile supports), style profile, tone/length directives, target template, language of the posting. The client LLM (user's Claude/Codex) drafts.
2. **`submit_asset(job_id, asset_type, content)`** stores + versions the draft. Assets are markdown/HTML with print-CSS templates (PDF via browser print; no server rendering in MVP).
3. **`ats_coverage_check(job_id, asset_id)`** — deterministic server-side: posting keywords vs asset text → covered / synonym / missing-but-have / genuine-gap table (ai-job-search's ATS check, no LLM needed).
4. **Reviewer pass as MCP prompt** — `/apply` guides the client to spawn its own second-look critique (drafter-reviewer separation on the client side, costs us nothing).
5. **Variants + calibration** — per-profile variation directives (tone/length/emphasis — port of card-26), and `record_outcome` feeds a calibration report: which variants/keywords correlate with interviews.

## Regional site intelligence: packs as live MCP updates

The MCP's knowledge of HOW to work each job site is **versioned data, deployed as updates** — not code releases:

- **Playbook packs per region/sector** (`packs/es.yaml`, `packs/de.yaml`, `packs/healthcare-uk.yaml`…): per-site search URL templates, navigation guidance for Claude-in-Chrome (where the filters are, how pagination works, login/captcha quirks), apply-form field maps (ported ats_form_maps + per-portal maps), and an `auto_apply_safe: true/false` flag per site (gates Autopilot).
- **Deployment:** hosted users get pack updates instantly (server-side deploy — the connector serves the new guidance on the next tool call, nothing to reinstall). Self-host: `packs update` pulls signed, versioned packs from the registry repo.
- **Crowd-learning loop (opt-in):** when the client LLM successfully navigates a site or completes a form — or hits a change that breaks the playbook — it calls `report_playbook_result` with a structured diff (what worked, what moved, new selectors). Aggregated reports feed the next pack version via maintainer/CI review. The MCP literally learns sites from real usage across the user base.
- **Community contribution:** a pack is a PR — schema validator in CI + a live probe checklist (`/add-portal`-style scaffolding command generates the skeleton and test-drives it with Claude-in-Chrome).

## Browser-apply orchestration protocol (how tools + prompts guide Claude-in-Chrome)

**Model: the MCP server is the choreographer, the client LLM is the actor.** The server holds state, playbooks, profile facts, and the consent policy; it never touches the browser. The client executes browser actions and reports back. Guidance is an **interactive loop**, not a one-shot plan (today's static `fill_plan` can't survive multi-page forms, screener questions, or selector drift).

### The apply loop (tool-by-tool)

1. **`start_application(match_id, variant?)`** — server-side preflight, all deterministic: dedup gate (`check_seen` — already applied → block/warn), daily cap + autopilot policy check, portal/ATS resolution from the URL, playbook load (form map, navigation quirks, `auto_apply_safe`), candidate data assembly (profile fields, form answers, assets). Returns an **application session**: `{application_id, state: draft, apply_method, consent_level, steps[], next_action}`.
2. **Step plan format** — ordered steps, each: `{step_id, kind: navigate|detect|fill|upload|answer|review|submit|verify, instruction (natural language for the LLM), selectors[] (ordered candidates from the pack), value | value_ref (profile field / asset id), fallback_hint, evidence: none|screenshot}`. The client executes steps in the user's browser.
3. **`report_apply_progress(application_id, step_id, status: ok|blocked|mismatch, observed?)`** — the heartbeat. Server responds with the next step(s), a **repair** (alternate selectors, "form is multi-page → here is the page-2 map"), or an obstacle route. Selector mismatches with the client's observed DOM hints are captured for the pack-learning loop.
4. **`resolve_field(application_id, field_label, field_type, options?)`** — for screener questions the pack didn't predict. Server answers deterministically from profile/form_answers/achievements when it can; otherwise returns `ask_user` + a suggested answer the human confirms in chat. Confirmed answers are **saved to the profile** so the question is never asked twice (progressive profiling in the wild).
5. **`get_asset_file(asset_id)`** — resolves the CV/cover file for upload steps (local path on self-host; short-lived signed URL on hosted — client fetches it before the upload step).
6. **Obstacles** — a step or report can return `obstacle: captcha|login|2fa|hostile_bot_check`: the client pauses and asks the human to resolve it in their own browser (they are present — it's their session), then resumes the loop. Captchas are always human-solved, never bypassed. (Today's `unblock_source` pattern, generalized.)
7. **`request_submit(application_id, summary, evidence?)`** — the consent gate, graduated: L0 → returns `await_human` ("show the filled form; the human clicks Submit"); L1/L2 with policy pass (score ≥ threshold, cap not reached, source allowlisted) → returns `submit_authorized + audit token`. The submit step is only ever emitted by this tool — structurally impossible to reach without a consent check (testable invariant).
8. **`confirm_submitted(application_id, evidence)`** — server flips state, writes `record_application` (dedup hash), audit row, and schedules follow-up nudges. A `verify` step (confirmation page/email present?) closes the loop.
9. **`report_playbook_result(source, diff)`** — fired at session end (opt-in): what worked, what moved, new selectors → feeds the next pack version.

**Application state machine (server-side):** `draft → filling → awaiting_human | awaiting_submit → submitted → verified → tracked` (+ `abandoned` on timeout). Every transition audited.

### Prompts (the behavioral contract)

- **Server `instructions`** (MCP server-level, ports today's proven guidance pattern): the global contract — always follow `next_action`, never invent screener answers (use `resolve_field`), never bypass captchas, evidence discipline (screenshot after fill, before submit).
- **`/apply <match>`** prompt: runs the loop above end-to-end; defines when to talk to the human (obstacles, `ask_user` fields, L0 submit) and when not to interrupt (L2 batch).
- **`/hunt`** prompt: the search-side twin — `hunt_plan` → per-source playbook → navigate/extract in browser → `submit_findings` → `report_playbook_result` on drift.
- **`next_action` breadcrumbs on every tool response** keep the client on-protocol even mid-conversation (today's `guidance.py` pattern, proven to work).

## Autopilot Apply (opt-in)

- **L0 (default):** review each match; Claude pre-fills; human submits.
- **L1:** one-click approve → Claude fills AND submits that single application in the user's browser; user watches.
- **L2 (batch autopilot):** user sets a policy — min score, max N/day (ported card-26 cap), allowlisted `auto_apply_safe` sources, asset variant to use — and Claude works through the queue in their browser session, streaming progress, interruptible at any time. Every submission audited (`record_application` automatic) and deduped (`check_seen` gate before every apply).
- **Risk posture:** runs only in the user's own browser/session (no server-side robot → no board-level bot bans attributable to us), per-site allowlist keeps it off hostile portals, caps protect application quality and the user's reputation.

## Feature set

**MVP (launchable):** onboarding wizard (web + guided MCP `/setup` prompt) · profile + achievements bank · hunt plans from source packs (client browses, submits findings) · dedup + seen-tracking · fit scoring (sector-pack driven) · review queue + pipeline · generation briefs + assets + ATS check · supervised fill_plan · record_application/outcome · self-host (uvx/docker, SQLite, no auth) · hosted (remote MCP + OAuth connector, dashboard, magic-link, Stripe $5).

**v1 (differentiators):** **Autopilot Apply L1/L2** (policy-driven, user's browser) · **crowd-learning playbook loop** (`report_playbook_result` → pack updates) · `/interview` prep packs from the application archive · `/upskill` gap analysis · calibration reports · community source-pack registry + `packs update` · pack scaffolding command (ai-job-search `/add-portal` equivalent) · `.mcpb` one-click bundle for Claude Desktop · connectors-directory listing.

## MCP surface (~26 tools + prompts)

- **Profile:** `get_profile`, `update_profile`, `list_profiles`, `set_active_profile`, `add_achievements`, `set_style_profile`, `import_from_url_findings` (guided LinkedIn/GitHub import)
- **Hunt:** `hunt_plan`, `source_playbook`, `list_source_packs`, `submit_findings`, `check_seen`, `list_matches`, `get_match`
- **Review:** `approve_match`, `discard_match`
- **Assets:** `get_generation_brief`, `submit_asset`, `get_assets`, `ats_coverage_check`
- **Apply (orchestration loop):** `start_application`, `report_apply_progress`, `resolve_field`, `get_asset_file`, `request_submit`, `confirm_submitted`, `record_application` (manual/external applies), `record_outcome`, `set_autopilot_policy`, `autopilot_queue`, `report_playbook_result`
- **Insight:** `pipeline_stats`, `calibration_report`, `gap_report`
- **Meta:** `server_info` (version handshake, next-action guidance)
- **Prompts:** `/setup`, `/hunt`, `/review`, `/apply`, `/interview`, `/upskill`

## Hosted architecture ($5/mo)

- FastAPI + Postgres (RLS patterns ported) · MCP over streamable HTTP with OAuth 2.1 connector auth (authorization server = us) · thin Next.js dashboard (onboarding, pipeline, profile, billing — intelligence stays client-side) · Stripe (ported card-9 patterns; single $5 plan + free trial) · fair-use infra limits only (storage/findings counts), never LLM limits.
- Self-host parity: identical MCP over stdio, SQLite, `RADAR_LOCAL_MODE`-style no-auth, one-command install (`uvx` / `docker compose up`).

## Development harness: tweaked agents-specs template (deliberately light)

Source template: `~/Desarrollo/agents-specs` (spec-and-contract harness, ~15 transferable files, markdown-only, no installer — manual copy + placeholder fill). **We intentionally do NOT copy the heavyweight RIPER-5 vc-* system** — for a greenfield solo+agents repo, reviewers + backlog + TDD discipline ARE the quality gates. That choice is itself the anti-over-engineering decision.

**Copy + adapt (source → destination):**
| From template | To new repo | Tweak |
|---|---|---|
| `agents/sub-agents/test-auditor.md` | `.claude/agents/test-auditor.md` | Adapt frontmatter to Claude Code subagent format; enforce no-mocks discipline (real SQLite tmp_path, pytest-httpserver, recorded fixtures) |
| `agents/sub-agents/simplicity-reviewer.md` | `.claude/agents/simplicity-reviewer.md` | Embed the anti-over-engineering charter below as its P0-block rules |
| `agents/sub-agents/security-reviewer.md` | `.claude/agents/security-reviewer.md` | Add product-specific P0 surfaces: connector OAuth, session auth, RLS/tenant isolation, Stripe webhook, consent gate |
| `agents/sub-agents/code-reviewer.md` | `.claude/agents/code-reviewer.md` | As-is |
| `agents/workflows/final-review.md` | `.claude/agents/` or CLAUDE.md §gate | Reduce 5→4 reviewers (documentation-reviewer becomes on-demand, not a gate) |
| `projects/agent-templates/backlog/` (`agent_index.md`, `_TEMPLATE.md`, state dirs) | `backlog/` | As-is: `pending → in_progress (max 1/agent) → done → testing → production` + `decisions/` ADR log |
| `projects/agent-templates/codex-python-agent/CLAUDE.md` | `CLAUDE.md` | Rewrite condensed non-negotiables from this plan; must point to the newly authored `AGENTS.md` |

**Anti-over-engineering charter (binding; simplicity-reviewer enforces as P0):**
- No abstraction before the **second concrete use** (rule of two). No interface with a single implementation — `typing.Protocol` only at the named ports (§Architecture spec).
- New dependency = one written justification line on the backlog card; stdlib first. (Lesson: `headroom-ai` shipped in the old repo with zero imports.)
- No speculative features, no config option without a real user needing it (YAGNI). MVP biases stand: print-CSS PDF, single $5 plan (no tier engine), magic-link only.
- New layer / framework / architectural pattern not named in §Architecture spec → simplicity-reviewer P0-block; requires an ADR in `backlog/decisions/` to override.
- Prefer deleting code over configuring it. Every phase ends with a simplifier pass over the diff.

## Sprint plan (agile; each numbered item = one backlog card)

**Cadence rules:** sprints are scope-boxed (solo + AI agents — a sprint ends when its demo gate passes, target ~1 week each). Every card = one focused work session with the `_TEMPLATE.md` DoD checklist; every sprint ends with its **demo gate** + a **simplifier pass over the sprint diff** + the 4-reviewer final-review on each card. **Rolling-wave carding:** only the current and next sprint live as cards in `backlog/pending/`; later sprints stay as plan lines here until reached (no stale cards).

### Sprint 0 — Foundations (a repo that enforces its own rules)
- **S0.1** Repo bootstrap: git init (`main`), Apache-2.0, README stub, `pyproject.toml` (uv + hatchling), ruff.
- **S0.2** Harness install per §Development harness: 4 reviewers + final-review gate + backlog kit; author `AGENTS.md` + `CLAUDE.md`.
- **S0.3** Hexagonal skeleton (§Architecture spec) + import-linter boundary contracts + CI (lint · tests · contracts).
- **S0.4** Test harness conventions: no-mocks pytest, real-SQLite `tmp_path` fixture, live-Postgres marker, pytest-httpserver.
- **Demo gate:** CI green on the skeleton; final-review gate exercised end-to-end on one seed card.

### Sprint 1 — Data core (organ transplants, with their tests)
- **S1.1** DB port + SQLite adapter + migration runner (port dual-dialect + FK-safe recreation lessons).
- **S1.2** Postgres adapter + RLS multi-tenancy + SQLite/PG parity test matrix.
- **S1.3** `profiles` schema implementing the §Onboarding intake model (Tier 1 + Tier 2, achievements bank, style profile) + profile services.
- **S1.4** Dedup engine port: `canonical_url`, dedup hashes, `external_applications`, `check_seen`.
- **Demo gate:** one test suite green on BOTH backends; `check_seen` correct against ported fixtures.

### Sprint 2 — MCP v1: profile + hunt
- **S2.1** FastMCP stdio entrypoint + `server_info` + `next_action` guidance breadcrumbs on every tool response.
- **S2.2** Profile tools (get/update/list/set_active/add_achievements/set_style_profile/import_from_url_findings).
- **S2.3** Pack schema + CI validator + seed packs: migrate the 155 curated sources, re-tagged by structured country/sector.
- **S2.4** `hunt_plan` + `source_playbook` + `submit_findings` + sector-pack-driven scoring (no hardcoded tech filter) + `list_matches`.
- **Demo gate:** live Claude Code session — `/hunt` on one real portal: findings persisted, deduped, scored.

### Sprint 3 — Assets: briefs + honesty engine
- **S3.1** `get_generation_brief`: job extraction, keyword map, **facts inventory**, style directives.
- **S3.2** `submit_asset` + versioning + print-CSS templates.
- **S3.3** `ats_coverage_check` (deterministic, no LLM).
- **S3.4** Prompts `/setup` `/hunt` `/review` `/apply` + review tools (`approve_match`/`discard_match`).
- **Demo gate:** hunt → match → brief → client-LLM draft → coverage check flags a genuine gap WITHOUT keyword stuffing.

### Sprint 4 — Browser-apply orchestration loop
- **S4.1** Application state machine + `start_application` preflight (dedup gate, cap, playbook, candidate data).
- **S4.2** `report_apply_progress` loop + selector repairs + `resolve_field` with progressive profile save.
- **S4.3** `request_submit` L0 consent gate + `confirm_submitted` + `record_application`/`record_outcome` + `get_asset_file`.
- **S4.4** Obstacle routes (captcha/login pause-resume, human-solved) + `report_playbook_result` capture.
- **Demo gate:** one full REAL application via Claude-in-Chrome, human clicks Submit, complete audit trail.

### Sprint 5 — Self-host onboarding + packaging
- **S5.1** `/setup` guided MCP onboarding (Tier 1 < 3 min) + regex CV parser port (zero-LLM default).
- **S5.2** LinkedIn guided import + progressive Tier 2 prompts.
- **S5.3** CLI (`init`/`serve`) + uvx packaging + PyPI publish + `install.sh` served at mcpfor.work.
- **Demo gate:** clean machine → install → onboard → first hunt plan in < 10 min, zero server-side LLM calls.

### Sprint 6 — Hosted alpha
- **S6.1** Remote MCP (streamable HTTP) + accounts (magic-link port) + sessions.
- **S6.2** OAuth 2.1 connector authorization server (PKCE + dynamic client registration).
- **S6.3** Thin web dashboard: onboarding, pipeline, profile.
- **S6.4** GDPR export/delete port + audit log.
- **Demo gate:** connector added from the claude.ai UI end-to-end; same account works from Codex CLI; RLS probe green on live Postgres.

### Sprint 7 — Monetization + Autopilot
- **S7.1** Stripe $5 flat (checkout/portal/webhook ports) + fair-use infra limits.
- **S7.2** `set_autopilot_policy` + `autopilot_queue` + L1/L2 + daily caps + `auto_apply_safe` gating.
- **Demo gate:** test-mode subscription end-to-end; batch of 5 real applications under policy in a supervised probe.

### Sprint 8 — Learning loop + OSS launch
- **S8.1** `report_playbook_result` ingestion + pack-update pipeline (hosted live deploy; self-host `packs update`).
- **S8.2** Landing page (built from the companion design brief) + README/docs.
- **S8.3** `.mcpb` bundle + connectors-directory submission + community pack contribution guide + launch checklist.
- **Demo gate:** a playbook fix deployed server-side reaches a connected client without reinstall; public launch checklist complete.

**Post-launch backlog seeds (Sprint 9+, not carded yet):** `/interview` prep packs · `/upskill` gap analysis · calibration reports · pack scaffolding command (`/add-portal` equivalent) · signed binary installers.

## Verification

- Every sprint: no-mocks pytest suite green (SQLite + live-Postgres RLS markers), ruff clean, import-linter contracts pass, simplifier pass on the sprint diff, 4-reviewer final-review per card.
- Structural invariant tests: zero server-side LLM imports/calls in hosted paths; consent invariant — no submit-class step ever emitted without a recorded autopilot policy/approval; autopilot respects daily cap + `auto_apply_safe` allowlist + `check_seen` gate (tested); facts-inventory present in every brief.
- Sprint 6 probe: real Claude.ai connector OAuth + real Codex CLI session against staging.
- Launch gate: cold-install test by a non-technical user on hosted (no terminal), and by a dev via `curl mcpfor.work/install | sh`.

## Open items (decide during Sprint 0)
- Final package/CLI name (`mcpforwork`? binary name?).
- Whether the hosted free tier exists (e.g., 25 tracked findings) or trial-only.
- PDF rendering: print-CSS only (MVP) vs server-side deterministic rendering later.
