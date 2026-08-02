# AGENTS.md — source of truth for all agents and contributors

Everything here binds every coding agent (Claude Code, Codex, Cursor) and every
human contributor. [`CLAUDE.md`](CLAUDE.md) only adds Claude-Code-specific
notes; on conflict, this file wins. All prose, code, comments, and docs are
**English-only**.

The full product specification lives in
[docs/PRODUCT_PLAN.md](docs/PRODUCT_PLAN.md). Section references such as
"§Architecture spec" point there.

---

## 1. Product invariants (never violate)

1. **The LLM is the client.** No server-side LLM calls, ever. No
   `openai`/`anthropic` SDK importable from `domain/`, `services/`, `ports/`,
   or `packs/` — enforced by import-linter in CI.
2. **Graduated autonomy, consent-based.** Never submit without a recorded
   consent check: `request_submit` is the only place a submit directive can
   be issued, and consent artifacts (L1 approval, L2 policy) are written
   exclusively by the human-session HTTP API — never by an MCP tool
   (ADR 0005). Supervised (L0) is the default.
3. **Open-core.** Every feature works self-hosted on SQLite with no account.
   Hosted-only concerns (Postgres/RLS, Stripe, mailer) live behind ports.
4. **Never fabricate.** Every generation brief includes a facts inventory;
   drafts may only claim what the profile proves. Gaps are acknowledged,
   never stuffed.
5. **Sector/country logic is data, not code.** Site knowledge ships as
   versioned packs in `packs/`, updatable independently of releases.
6. **User owns their data.** Export/delete paths are mandatory for any new
   personal-data table; EEO data is optional and privacy-gated.

## 2. Architecture (pragmatic hexagonal)

```
src/mcpforwork/
  domain/       # PURE logic, no I/O; imports nothing from any other layer
  services/     # use cases; signatures (uow, user_id, ...); caller commits;
                # consent + caps + dedup gates live here
  ports/        # typing.Protocol seams ONLY: Database/UoW, Mailer, Billing,
                # FileStore, Clock
  adapters/     # driven implementations: db/{sqlite,postgres}, billing, mail, files
  entrypoints/  # driving, all thin (auth + serialization only): mcp, api, cli
  packs/        # DATA not code: country/sector source packs + schema validator
```

Boundary rules are enforced by `uv run lint-imports` locally and in CI —
architecture drift fails the build, not a review comment. Deliberately
skipped ceremony (do NOT introduce): interface-for-every-class, entity↔DTO
mapping layers, DI frameworks, ORM/repository-per-aggregate, microservices.

## 3. Anti-over-engineering charter (binding; enforced by the review gate)

- No abstraction before the **second concrete use** (rule of two). No
  interface with a single implementation — `typing.Protocol` only at the named
  ports.
- New dependency = one written justification line on the backlog card;
  stdlib first.
- No speculative features; no config option without a real user needing it
  (YAGNI). MVP biases stand: print-CSS PDF, single $5 plan, magic-link only.
- New layer / framework / architectural pattern not named in §Architecture
  spec → P0-block at the review gate; requires an ADR in `backlog/decisions/`
  to override.
- Prefer deleting code over configuring it. Every sprint ends with a
  simplifier pass over the sprint diff.

## 4. Testing contract (TDD, zero mocks)

- Per card: **spec → red → green → refactor → doc**. Failing test first.
- **No mocking frameworks** (`unittest.mock`, `MagicMock`, `@patch`,
  `monkeypatch`-as-stub, `responses`, `respx`). Instead:
  - **Database:** real SQLite file at pytest `tmp_path`; Postgres via
    `@pytest.mark.live` against a real local instance (Docker).
  - **HTTP / third parties:** `pytest-httpserver` local server; provider
    behavior via recorded fixtures from real interactions (e.g. Stripe events
    replayed with a real HMAC signature) — never invented responses.
  - **Time / randomness:** injected via arguments or the Clock port, never
    patched.
- Test names state the business rule, not the mechanics.
- Default run excludes the `live` marker; live + full suites are pre-push
  gates.
- Mutation testing: no `mutmut` dependency yet. The sanctioned substitute is
  the manual mutant probe — deliberately break the guarded behavior (remove
  the PRAGMA, add the forbidden import), observe the check fail, revert, and
  record both results on the card.

## 5. Backlog workflow

Canonical rules: [backlog/agent_index.md](backlog/agent_index.md).
Non-negotiables: backlog-first (card exists and is `in_progress/` before code
changes); at most one card in progress per agent; the card's folder IS its
state; sprint-style names `S<sprint>.<n>_slug.md`; rolling-wave carding (only
current + next sprint in `pending/`).

## 6. Review gate (single fused reviewer, on-demand extras)

A card may move to `done/` only after the fused reviewer subagent
[.claude/agents/test-code-reviewer.md](.claude/agents/test-code-reviewer.md)
(test audit + code review + regression audit, zero-mocks P0, `model: inherit`)
returns PASS on the card's diff, no P0/P1 finding remains, and every P2/P3
finding has a disposition (fixed, follow-up card, or written rejection).

The regression audit is part of the gate: the reviewer runs the FULL suite
(not just targeted tests) plus the structural gates (lint-imports, ruff, CI
consent grep, web no-LLM-deps guard) and fails the card if the change weakens
or breaks any previous contract, test, gate, or process.

- Simplicity and security reviews are ON-DEMAND: the user or the agent may
  request them explicitly (e.g. §9 P0 surfaces); they are not a per-card gate.
  See [ADR 0007](backlog/decisions/0007_single_reviewer_gate.md).
- If the subagent cannot be spawned, perform one clearly labeled review pass
  with the same contract and disclose the degraded mode.

**Closure semantics:** `done/` = implemented + gate passed · `testing/` =
verification gates run (full suite + real smoke test, evidence recorded) ·
`need_human_testing/` = final proof needs the human · `production/` = deployed
+ post-deploy checks passed. A task is not closed merely because code was
written.

**Documentor step (mandatory at close).** After the gate passes and before
the closing commit, spawn the documentor subagent
[.claude/agents/documentor.md](.claude/agents/documentor.md) on the card: it
writes/updates the granular module docs under `docs/` (how the feature was
developed, invariants, decisions, gotchas) and fixes drift in docs it
touches. The docs it writes ride the card's closing commit. The index is
[docs/README.md](docs/README.md).

## 7. Commits

- Conventional Commits, on `main`.
- Stage **only the task's files by explicit path** — never `git add -A`,
  `git add .`, or `git commit -a`.
- Closing commit per card: touched code + the moved card file.
- Push is a separate gate: full suite green first.

## 8. Commands

```bash
uv sync                                  # install / update environment
uv run pytest                            # default suite (live excluded)
uv run pytest -m live                    # live arm (needs Docker Postgres)
uv run ruff format . && uv run ruff check .
uv run lint-imports                      # architecture boundary contracts
```

## 9. Security P0 surfaces

Connector OAuth (2.1 + PKCE + dynamic client registration), magic-link/session
auth, RLS/tenant isolation (user context set before any query; fail-closed),
Stripe webhook signature verification, the consent gate, autopilot caps +
`auto_apply_safe` allowlist, and the zero-server-side-LLM invariant. Any change
touching these warrants an explicit on-demand security review pass (ADR 0007) —
request it before closing the card.
