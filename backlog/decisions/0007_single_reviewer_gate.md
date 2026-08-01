# ADR 0007 — Single fused reviewer gate (test + code + regressions)

**Date:** 2026-08-01
**Status:** accepted (supersedes the review-gate part of ADR 0001 decision 3)

## Context

ADR 0001 installed a 4-reviewer final-review gate (test-auditor, code-reviewer,
simplicity-reviewer, security-reviewer) as the quality harness for a
solo+agents greenfield repo. After 30+ cards, the marginal value of four
separate passes per card no longer pays for its latency, and the project is
entering a long autonomous execution window (the self-host E2E plan) where the
user wants exactly one strong automatic gate — plus an explicit regression
audit so new cards never break previous engineering or processes.

## Decision

1. **One automatic gate.** `.claude/agents/test-code-reviewer.md` fuses the
   test-auditor and code-reviewer contracts and adds a mandatory regression
   audit. A card moves to `done/` only after this reviewer returns PASS on the
   card's diff (no P0/P1 open; P2/P3 dispositioned).
2. **`model: inherit`.** The reviewer runs on the same model the main agent is
   using in Cursor — no pinned external model.
3. **Regression audit is part of the gate (P0).** The reviewer runs the FULL
   suite (not just targeted tests) plus the structural gates (lint-imports,
   ruff, CI consent grep, web no-LLM-deps guard) and fails the card if the
   change weakens or breaks any previous contract, test, gate, or process
   (backlog-first, TDD evidence, DoD honesty).
4. **Simplicity and security reviews are on-demand**, not a per-card gate. The
   user or the agent may request them explicitly (e.g. AGENTS.md §9 P0
   surfaces); the main agent then performs a clearly labeled pass with the
   corresponding criteria (recoverable from git history of
   `.claude/agents/simplicity-reviewer.md` / `security-reviewer.md`).
5. The four old agent files are deleted; their contracts live on in the fused
   file (test + code) and in git history (simplicity + security).

## Consequences

- `AGENTS.md §6`, `CLAUDE.md`, `backlog/agent_index.md §4/§7` and
  `backlog/_TEMPLATE.md` are updated to name the fused gate.
- The E2E plan's references to a "final-review gate (all four reviewers)" and
  to security-reviewer as a phase gate are superseded by this ADR; on-demand
  security passes will be requested explicitly on the consent/autopilot cards.
- Reversing this decision = new ADR restoring a multi-reviewer gate.
