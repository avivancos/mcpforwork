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

## Carried follow-ups (from the S0 final-review gate)

- When Sprint 2 is carded, S2.1 must add the entrypoint-independence
  import-linter contract ("entrypoints never import each other") — deferred
  under the rule of two until a second entrypoint exists.

## Carried follow-ups (from the S1 final-review gate)

- **[before any hosted deploy — security P2]** The Postgres `app` role ships
  with a hardcoded dev/test password (`app_secret`) in
  `pg/001_initial.sql`. It is the RLS tenant boundary. The hosting/deploy card
  (S6) MUST provision the role out-of-band with a secret password (the
  migration's `IF NOT EXISTS` guard means a pre-provisioned role is not
  clobbered), or make the migration env-var-driven and fail-closed in prod.
  Rerun security-reviewer then.
- **[S2 — FK-recreate must preserve RLS]** When S2 FK-recreates
  `external_applications` to add the `finding_id` FK to `explore_findings`, the
  recreation drops `ENABLE/FORCE ROW LEVEL SECURITY` + the policy — they MUST be
  re-added. The new fail-closed live test guards this (it fails if RLS is lost).
- **[S6.4 — audit_log read access]** `audit_log` is intentionally not
  FORCE-RLS'd and now stores per-tenant data (applied URLs). Before any read
  path over it ships, scope it by `user_id` or add a read-side RLS policy.
- **[hosting/pool card — session-GUC footgun]** `set_user_context` uses a
  session-scoped GUC, correct for the fresh-per-request-connection model. If
  connection pooling is introduced, enforce reset-on-checkout and add a test
  proving a recycled connection fails closed.
- **[note, no action]** `_pg_statements` does not track single-quoted literals
  (no current migration triggers it). Revisit if a literal with `;`/`$`/`--`
  appears.

## Carried follow-ups (from the S2 final-review gate)

- **[S4 — apply/prefill card]** `apply_playbook` URLs (returned by
  `source_playbook`) are NOT scheme-validated the way `url_template`/`base_url`
  now are. No live path today (only the text `ats_hint` is read; nothing opens
  an apply URL yet). When the client opens an apply URL, scheme-validate it in
  `domain/packs.validate_pack` the same way.
- **[note, low priority]** Timestamp string shape differs across backends:
  SQLite emits `…Z` (ms, UTC), Postgres emits `…` (µs, no offset, naïve
  TIMESTAMP). Both are valid ISO-8601 and both satisfy consumers today. If a
  strict client needs a uniform shape, normalise timestamps to `…Z` at the
  service deserializers (or store `timestamptz` on PG).
- **[note, low priority]** `_json_default` (MCP entrypoint) falls back to
  `str(obj)` for any non-datetime type — defensive against crashes but would
  silently stringify a future genuinely-wrong type (e.g. a `Decimal` money
  column, none exists until billing S7). Revisit when a NUMERIC column lands.
- **[still deferred — rule of two]** The entrypoint-independence import contract
  ("entrypoints never import each other") lands when the second entrypoint
  (API/CLI) exists. The guidance-purity contract was added in S2.
