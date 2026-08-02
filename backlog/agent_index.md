# Backlog — canonical rules (source of truth)

> Portable backlog system. This file is the **source of truth for inviolable
> backlog rules**; `AGENTS.md` points here. Project parameters: run environment
> = **uv on the host, Docker only for live services (Postgres)**; documentation
> language = **English**; default branch = **main**.

A backlog is a set of task files (`.md`) that move between **state folders**.
The current state of a task **is** the folder it sits in — nothing else.

---

## 1. Read-before-work (master rule)

Before any exploration, edit, or proposal the agent **lists open work**
(`pending/` + `in_progress/` only; never `decisions/` as pending), shows the
user a one-line summary per task, and **waits** for an explicit instruction on
which task to attack. The only override is the user literally saying "ignore
the backlog".

---

## 2. States & flow

```
pending/             # not started
in_progress/         # active — at most ONE per agent at a time
done/                # implemented + fused review gate passed, NOT yet fully verified
need_human_testing/  # implemented, verification blocked on the human (fork of done/)
testing/             # verified by the agent (full suite + smoke evidence)
production/          # deployed
decisions/           # ADR-style decision log (not a work state)
```

Mandatory flow — **move the `.md` file** between folders, never skip a state
without explicit human authorization:

```
pending → in_progress → done → testing → production
                          └──→ need_human_testing → testing/production
```

- **One in-progress per agent.** Don't pull a second card while one is active.
- **Naming:** sprint-style — `S<sprint>.<n>_short_slug.md` (e.g.
  `S0.1_repo_bootstrap.md`). Non-sprint follow-ups use plain increasing
  numbers (`101_short_slug.md`).
- **Rolling wave:** only the current and next sprint live as cards in
  `pending/`; later sprints stay as plan lines in `docs/PRODUCT_PLAN.md` until
  reached.

---

## 3. Spec-driven + TDD (zero mocks)

Every formal task: **Spec → red test → green code → refactor → doc → move**.
Write the failing test first (for bug fixes, a test that reproduces the bug),
then the minimum code to pass, then refactor.

**No mocking frameworks.** External dependencies are exercised for real:
database via a real SQLite file at pytest `tmp_path` (live Postgres behind
`@pytest.mark.live`), HTTP via `pytest-httpserver` serving recorded fixtures
from real interactions, time and randomness injected via arguments or the
Clock port. Full contract: `AGENTS.md §Testing contract`.

---

## 4. Task closure — Definition of Done

A card may move to `done/` only when **all** hold:

1. **Targeted tests green** via `uv run pytest <paths>` (the tests for the
   touched module/feature; the full suite is a pre-push gate, not a per-task
   one).
2. **Fused review gate passed:** the fused reviewer
   (`.cursor/agents/test-code-reviewer.md`, `model: inherit`) returned PASS on this card's diff —
   including the regression audit (full suite + structural gates green, no
   previous contract/test/gate weakened); no P0/P1 open; every P2/P3
   dispositioned (fixed, follow-up card, or written rejection). See
   `AGENTS.md §6` and ADR 0007. Simplicity/security reviews are on-demand.
3. **Post-task audit:** navigable UI → visual audit; no UI → smoke-test the
   touched tool/endpoint/CLI (status + schema + sane latency).
4. **Improvements noted** → recorded in the card's `## Improvements noted`
   section **and** raised as follow-up tasks.
5. **New dependencies justified** — one written line per new dependency on the
   card (anti-over-engineering charter).
6. The `.md` is moved to `done/` (or `need_human_testing/`).
7. **Closing commit** on `main`, conflict-free, staging **only this task's
   files by explicit path** (touched code + the moved `.md`) — never
   `git add -A` / `git add .` / `git commit -a`. Unrelated working-tree changes
   stay unstaged. Conventional Commits format.

Push is a separate gate and requires the **full suite** to pass first.

---

## 5. `need_human_testing/` — verification blocked on the human

Use this fork when implementation is finished but the **final proof needs an
action only the human can take**: real money movement, real applications
submitted to third parties, credentials/2FA/accounts only the human holds, a
manual step in a third party (job portal, Stripe dashboard, registry…), or
legal/business sign-off the agent must not assume. If the agent **can** verify
it, do not use this state — verify and move to `testing/`.

Before moving here, the card must include a `## Pending human testing` section
with: (1) what was built and why the agent can't close verification; (2) exact
reproducible steps for the human (paths, commands, data, which account);
(3) expected result + pass/fail criteria; (4) risks to watch (money, real data,
irreversible); (5) what the agent already verified. Outcome: pass → `testing/`
(or `production/` if deployed); fail → back to `in_progress/` with failure
notes.

---

## 6. `decisions/` — decision log

ADR-style folder. One file per non-trivial, hard-to-reverse decision: context,
the options weighed, the choice, and the consequence. Not a work state; never
counted as pending. Overriding the anti-over-engineering charter's
architecture freeze requires an ADR here.

---

## 7. Task file format

Every task file follows this skeleton (see `_TEMPLATE.md` to copy). All prose
in English.

```markdown
# S<sprint>.<n> — <short imperative title>

**Epic:** <epic / area>
**Estimated effort:** <~X h>

## Goal
<What and why, 2–4 lines. The outcome, not the implementation.>

## Spec
<Contracts, schemas, endpoints, validations, the exact expected behavior.
This is what makes the task verifiable.>

## Files to create/modify
- `path/to/file` — note (NEW if created)

## Dependencies added
<!-- one justification line per new dependency, or "None" -->

## Definition of Done
- [ ] <verifiable acceptance criterion>
- [ ] Targeted tests green via `uv run pytest <paths>`
- [ ] Fused review gate: test-code-reviewer PASS (incl. regression audit)
- [ ] Post-task audit done (visual for UI / smoke for tool/API/CLI)

## Improvements noted
<!-- fill during execution; raise a follow-up task per item -->

## Pending human testing
<!-- ONLY when moving to need_human_testing/. Steps, expected result,
     pass/fail criteria, risks, and what the agent already verified. -->
```
