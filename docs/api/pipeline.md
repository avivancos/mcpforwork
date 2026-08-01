# Pipeline read API

> Read side of the dashboard: `GET /v1/pipeline`, `GET /v1/pipeline/stats`,
> `GET /v1/matches/{id}`, plus the `pipeline_stats` MCP tool — one service,
> two thin wrappers. Built by S6.9 (read windows: SQL aggregation + audit
> pre-filter), S6.6a (service + routes + MCP tool).

## How it works

**Service** — `src/mcpforwork/services/pipeline.py` (read-only; the caller
owns the transaction). Contract source of truth: `web/src/lib/api/types.ts` —
ISO-8601 timestamps, string ids; the web humanizes at render.

- `derive_stage(finding_status, application)` (pipeline.py:47) — the PURE
  stage mapping and single source of the stage vocabulary: `discarded` wins
  even with an application; an outcome maps via `_OUTCOME_STAGES`
  (pipeline.py:25, `no_reply`→`no_response`, `hired`→`offer` — the web has no
  hired chip); `awaiting_human`/`submit_requested` → `awaiting_you`;
  `draft`/`filling` → `filling`; `submitted`/`verified` pass through;
  `abandoned` falls back to `new_match`.
- `_latest_applications` (pipeline.py:68) — finding_id → newest application
  row in ONE query (`MAX(id)` per finding, joined back), both dialects.
- `list_pipeline` (pipeline.py:107) — PipelineItem[] best-score-first
  (`LIMIT 200`, pipeline.py:100). `_item` (pipeline.py:80) sets
  `consent: "supervised"` only while an application is active (non-abandoned),
  `updated` from the application when active else the finding's `last_seen`,
  and `needsYou` (reason per application state, `_NEEDS_YOU` pipeline.py:34)
  only on `awaiting_you`.
- `pipeline_stats` (pipeline.py:169) — counts aggregated IN SQL over ALL the
  user's findings (`_STAGE_COUNTS_SQL`, pipeline.py:143): no row window.
  `_STAGE_CASE_SQL` (pipeline.py:125) is the SQL mirror of `derive_stage`;
  `foundThisWeek` counts new_match rows with `first_seen >= week_start`, where
  `_iso_ms_z` (pipeline.py:112) formats the boundary in the exact shape
  SQLite's strftime defaults write (fixed-width ms + `Z`), so lexicographic
  text comparison IS chronological on SQLite and PG coerces the same string to
  TIMESTAMP. Buckets: `newMatches`, `needsYou`, `submitted` (with `verified`),
  `responses` (`count`/`of`/`interviews` via the stage sets at
  pipeline.py:40-44). `now` is injectable.
- `get_match_detail` (pipeline.py:190) — MatchDetail or None when the finding
  is not the caller's (cross-tenant reads are indistinguishable from missing;
  the web's `getOrNull` maps 404 → null). Composes the item plus pack slug,
  posting URL, `constraintChecks` from the score breakdown, a dedup line, and
  generated assets. `employmentType` is `""` — not stored on findings, never
  fabricated. Audit events come from `audit_log` filtered by `user_id`
  explicitly (audit_log is NOT RLS-forced — ADR 0001 ledger; that filter is
  the tenant wall) with a finding-scoped LIKE PRE-FILTER (pipeline.py:205-218)
  keyed on the exact `"key": value` shape `json.dumps` writes
  (`%"finding_id": N%` plus `%"application_id": N%` when an application
  exists); `_finding_audit` (pipeline.py:244) then applies the exact per-row
  Python filter, so over-matches (finding_id 51 vs 5) are rejected and no
  event is ever crowded out by unrelated audit volume.

**Routes** — `src/mcpforwork/entrypoints/api/app.py`: the three GETs
(app.py:406-429), all behind `_authed`; `get_match` returns 404 for unknown OR
foreign ids.

**MCP tool** — `pipeline_stats()` in
`src/mcpforwork/entrypoints/mcp/server.py:366` — a thin wrapper over the same
service via `_tenant_uow`.

## Design decisions

- **SQL aggregation over Python-counting a capped window** (S6.9): the S6.6a
  review gate flagged two silent truncations — stats over a 1000-row window
  and match-detail audit over the user's last 200 rows. Both removed: stats
  aggregate per-stage in the database; the audit read is finding-scoped.
- **LIKE pre-filter over an `audit_log.finding_id` migration** (the card left
  it open): the LIKE is a superset pre-filter and the exact Python filter is
  unchanged, so no event is lost and no migration/call-site churn was needed.
- **`derive_stage` stays the source of truth**; the SQL CASE must mirror it —
  pinned by a seeded-matrix parity test on both dialects.
- **`_iso_ms_z` shape chosen empirically** (probed via psycopg): one string
  that sorts correctly as SQLite text AND casts cleanly to a PG timestamp.

## Testing

`tests/test_pipeline_api.py` (TestClient + `any_uow` dual-dialect arms, zero
mocks):

- Stage derivation unit tests for every branch (discarded-with-application,
  no-application, filling, awaiting_you, submitted→verified, outcome mapping,
  abandoned → new_match).
- Contract shape: pipeline mirrors types.ts, no consent badge without an
  application, stats count the derived stages, match detail composes assets +
  audit, 404 for unknown/foreign, cross-tenant list isolation.
- Tenant wall: `test_match_detail_audit_never_leaks_another_users_rows` is
  adversarial — the foreign row references the CALLER's finding, so only the
  SQL user_id filter stands (both dialects via `any_uow`).
- S6.9 windows: `test_stats_stay_correct_beyond_the_old_1000_finding_window`
  (seeds 1005), `test_match_detail_audit_is_complete_beyond_200_unrelated_rows`
  (250 unrelated newer rows + an adversarial over-match row),
  `test_stats_sql_stage_case_agrees_with_derive_stage_on_a_seeded_matrix`
  (320 combos: 5 finding statuses × 8 app states × 8 outcomes, incl. `""` and
  unknown outcomes), plus the gate-added killers
  `test_stats_never_count_another_users_findings` and
  `test_stats_use_the_latest_application_per_finding`.
- `test_pipeline_stats_mcp_tool_reads_the_same_service` covers the MCP wrapper.
- The live-PG arm serializes with `default=str` (entrypoint-style) — plain
  `json.dumps` breaks on PG datetimes (S6.6a gate fix).

## Gotchas

- `audit_log` is NOT RLS-forced: EVERY audit read must filter `user_id`
  explicitly. Forgetting it is a cross-tenant leak; the adversarial tests only
  guard the existing call sites.
- The LIKE pre-filter depends on `json.dumps`' exact `"key": value` spacing —
  a detail written with different spacing (e.g. `json.dumps(..., separators=)`)
  would evade the pre-filter. The exact Python filter still protects
  correctness of what IS matched, but events could be missed; keep audit
  writes on the default `json.dumps` (as `services/audit.py` does).
- `list_pipeline` still caps at 200 findings (pipeline.py:107) — fine at MVP
  scale; revisit with pagination.
- An early `_iso_ms_z` draft used `%f` (microseconds) where seconds belonged —
  SQLite accepted the malformed text silently, PG's timestamp cast rejected
  it. The dual-dialect parity tests earn their keep.
- `hired` renders as `offer` until the web grows a hired chip
  (pipeline.py:24-31).
