# CLAUDE.md — Claude Code complement

> **Read [`AGENTS.md`](AGENTS.md) first — it is the source of truth.** This
> file only adds Claude-Code-specific operational notes. Everything in
> `AGENTS.md` (product invariants, hexagonal boundaries, anti-over-engineering
> charter, zero-mocks TDD, backlog workflow, final-review gate, explicit-path
> commits) applies verbatim here. On conflict, `AGENTS.md` wins.

The same suite is read by **OpenAI Codex** and **Cursor** via `AGENTS.md`;
when you change an obligation, mirror it.

---

## Quick contract (the non-negotiables, condensed)

1. **Backlog-first.** Card in `backlog/pending/` → moved to `in_progress/`
   before touching code. Lifecycle and states: `backlog/agent_index.md §2`
   (the folder a card sits in IS its state). Override only if the user says
   "ignore the backlog".
2. **TDD, ZERO mocks.** Red → green → refactor. Real SQLite at `tmp_path`,
   live Postgres behind `@pytest.mark.live`, `pytest-httpserver` + recorded
   fixtures for HTTP, time/seed injected. Details: `AGENTS.md §4`.
3. **Anti-over-engineering charter is P0.** Rule of two, one justification
   line per new dependency, YAGNI, architecture freeze. `AGENTS.md §3`.
4. **Product invariants are structural.** Zero server-side LLM, consent gate,
   open-core SQLite parity, facts inventory, packs-as-data. `AGENTS.md §1`.
5. **At close:** targeted tests green → final-review gate (all four reviewers
   PASS) → move card to `done/` → Conventional Commit staging only this task's
   files by explicit path.

## Claude Code specifics

- **Final-review gate:** the four reviewers are Claude Code subagents in
  [.claude/agents/](.claude/agents/) — `test-auditor`, `code-reviewer`,
  `simplicity-reviewer`, `security-reviewer`. Spawn all four in parallel on
  the card's diff; collect the required-output reports; fix P0/P1; rerun
  affected reviewers. A documentation reviewer is on-demand, not a gate.
- **Plan first** for non-trivial cards (plan mode); get sign-off before
  writing code.
- **Before saying "done":** run the `AGENTS.md §8` commands and report what
  you actually observed — never assume a check is green.

## Commands

```bash
uv sync · uv run pytest · uv run ruff format --check . · uv run ruff check . · uv run lint-imports
```
