# ADR 0001 — Bootstrap decisions (package name, layout, harness)

**Date:** 2026-07-11
**Status:** accepted

## Context

Fresh English-first repo for mcpfor.work, pivoted from startup-jobs-radar
(Coverpilot) per `docs/PRODUCT_PLAN.md`. Several naming and structural
decisions had to be fixed before any code existed.

## Decisions

1. **Package name `mcpforwork`** (import name and distribution name). The
   plan lists the final package/CLI name as an open item to settle during
   Sprint 0; `mcpforwork` is the working name and stands unless revisited
   before the first PyPI publish (S5.3). CLI binary name is deferred to S5.3.
2. **Pragmatic hexagonal layout** exactly as §Architecture spec:
   `domain / services / ports / adapters / entrypoints / packs` under
   `src/mcpforwork/`. Boundary rules enforced by import-linter, not
   convention. Full Clean-Architecture ceremony deliberately rejected.
3. **Harness = 4-reviewer gate, not RIPER-5.** Reviewers adapted from
   `~/Desarrollo/agents-specs` into `.claude/agents/`; documentation-reviewer
   is on-demand, not a gate. The final-review workflow is condensed into
   `AGENTS.md §6` instead of a separate workflow file — one fewer document to
   drift.
4. **Run environment:** uv on the host; Docker only for live services
   (Postgres for `-m live` tests). Not Docker-only — this repo has no runtime
   service dependencies in its default test suite.

## Consequences

- Renaming the package later means a coordinated rename of `src/mcpforwork`,
  pyproject, and import-linter contracts — cheap before S5.3, expensive after.
- Any new layer or pattern beyond decision 2 requires a new ADR here
  (anti-over-engineering charter, architecture freeze).

## Open items still pending (from §Open items)

- Hosted free tier (e.g. 25 tracked findings) vs trial-only — decide by S6/S7.
- PDF rendering: print-CSS only (MVP bias stands) vs server-side later.
