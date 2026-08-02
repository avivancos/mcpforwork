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
- **[S6.4 — audit_log read access] — RESOLVED (S6.4).** `audit_log` is
  intentionally not FORCE-RLS'd and stores per-tenant data (applied URLs). The
  only read path, `services/privacy.export_user_data`, filters every table
  (audit_log included) by `user_id`; `tests/test_privacy_rls_live.py` proves on
  live PG, as the restricted `app` role, that an unscoped audit_log read returns
  both tenants (`[1,1,2,2]`) while the scoped export returns only the caller's.
  Any FUTURE read path over audit_log must apply the same explicit scoping (it is
  not covered by RLS).
- **[hosting/pool card — session-GUC footgun]** `set_user_context` uses a
  session-scoped GUC, correct for the fresh-per-request-connection model. If
  connection pooling is introduced, enforce reset-on-checkout and add a test
  proving a recycled connection fails closed.
- **[note, no action]** `_pg_statements` does not track single-quoted literals
  (no current migration triggers it). Revisit if a literal with `;`/`$`/`--`
  appears.

## Carried follow-ups (from the S2 final-review gate)

- **[CLOSED by S7.2c]** `apply_playbook.form_url_pattern` is now
  https-only in `domain/packs._validate_apply_playbook` (unknown keys
  rejected; http/javascript/data rejected). Clients open these URLs;
  see `docs/modules/packs.md`.
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

## Carried follow-ups (from the S6.4 final-review gate)

- **[hosted/headless — security P2→P1 there]** `delete_my_data(confirm=True)` is
  an irreversible account wipe gated only by a client-controlled boolean. On
  self-host this is proportionate (the MCP client surfaces destructive tool calls
  for human approval, and untrusted content sits in the same LLM context only
  under the human's eye). In any FUTURE headless/hosted path that invokes tools
  without per-call human approval, this becomes P1: an injected instruction in
  untrusted job-posting content could steer the client to call it. Before that
  ships, add an out-of-band confirmation (e.g. a token from a dry-run the human
  echoes) — mirror the L0 `request_submit → await_human` pattern for erasure.
- **[note — done in S6.4]** Erasure now also unlinks the on-disk asset files
  `get_asset_file` materialized (`data_dir/assets/{id}_{type}.md`), scoped to the
  user's own generated_assets so it stays multi-tenant-safe; the "nothing is
  kept" promise is literally true. No audit tombstone is written (a row
  referencing a deleted user would violate the FK); revisit a tenant-less
  tombstone (`user_id=NULL`) for hosted abuse-forensics.

## Carried follow-ups (from the S4 final-review gate)

- **[note — hosted PG]** `_today_started_count` compares a UTC day string
  against `created_at`; correct while PG runs UTC (the test container does).
  A non-UTC hosted PG shifts the daily-cap window — normalise (timestamptz or
  set the DB timezone) on the hosted deploy card (S6).
- **[written rejection — kept vocabulary]** `verify` step kind, the
  `submitted → verified` transition, and the `draft`/`abandoned` states are
  defined but not yet wired (confirmation-page check is a plan feature; an
  abandon_application tool is carded). Wire or drop by S8.
- **[note]** `applications.apply_method` is write-only until the S8 calibration
  reads it. `resolve_field(field_type)` param is card-specified, unused today.
- **[fixed in-gate]** State machine now ENFORCED in services (submit_requested
  state added: awaiting_human → submit_requested → submitted; no post-submit
  regression); resolve_field answers only a strict candidate-label allowlist
  and saved answers take precedence; applications/playbook_reports RLS live
  tests + S4 tool-layer fresh-connection tests added.
