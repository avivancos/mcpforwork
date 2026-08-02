# Hunt pipeline (plan → ingest → score → matches)

> The search side of the copilot: from the active profile + packs, produce
> per-source search playbooks the client LLM browses in the user's own browser;
> ingest the findings it extracts (deduped across BOTH application stores,
> scored against the profile, persisted); surface the matches. The server never
> browses — it choreographs. Built by S2.4; `mode` surfacing added by S2.6;
> `apply_hint` / full `apply_playbook` from packs (S7.2c).

## How it works

**Storage.** Migration v4 (`adapters/db/migrations.py:121-168`) creates
`explore_findings` (dedup_hash UNIQUE per user, url/title/company/location/
remote_scope/salary_text/description, score + JSON score_breakdown, status,
action, first_seen/last_seen) and — by SQLite table-recreate, PG
`ADD CONSTRAINT` — adds the S1.4-deferred `external_applications.finding_id`
FK to it.

**Plan.** `hunt_plan(uow, user_id)` (`services/hunt.py:46-72`): active profile
→ query = first two target titles → `registry.sources_for` filtered by
work_auth_countries / sectors / `_wants_remote` (`hunt.py:35-43`: `["remote"]`
→ True, no "remote" → False, mixed → None) → per-source
`{slug, name, mode, search_url, result_hint, apply_hint}` where
`apply_hint` is `PackSource.apply["ats_hint"]` when present. No profile →
`{error}`. `source_playbook(slug, query)` (`hunt.py:75-90`) returns the full
`apply_playbook` dict alongside search fields; `list_sources(countries,
sectors)` (`hunt.py:93-107`) is pack-only — no DB.

**Ingest.** `submit_findings(uow, user_id, source_slug, findings)`
(`hunt.py:110-203`). Per finding: skip non-mapping items, blank titles, and
non-http(s) URLs; `dedup_hash(url)`; skip as `seen_again` when the hash is in
`external_applications` (already hand-applied — never re-enters the pipeline);
on a re-sight of an existing finding, MERGE the new extraction over the stored
one (`_DESCRIPTIVE_FIELDS`, `hunt.py:25-32` — a sparser re-sight never erases
richer data), re-score, bump `last_seen`; otherwise score + insert with
status `new`. Returns `{submitted, new, seen_again, skipped}` and writes an
audit row. Unknown source → `{error}`.

**Scoring.** `domain/scoring.py` is PURE and profile-driven — deliberately NOT
the donor's hardcoded tech persona. `score_finding(finding, profile,
sector_terms=())` (`scoring.py:56-79`) tokenizes the profile's target_titles
and sectors (`_terms`, `:38-45`: lowercase word tokens, len ≥ 3, stopwords
out) and weights five dimensions: title hits (cap 4 × 12), sector hits
(cap 3 × 8), remote match (10), seniority mention (10), salary signal (8 —
`salary_text` or a compensation regex over the text). Capped at 100, with the
per-dimension `breakdown` persisted as JSON. `determine_action`
(`scoring.py:82-88`): ≥70 `strong`, ≥40 `review`, else `new`. An empty profile
scores only on remote/salary — it never invents relevance.

**Read.** `list_matches(uow, user_id, min_score=0, status=None, limit=50)`
(`hunt.py:213-228`) orders by score DESC, id DESC and deserializes the
breakdown; `get_match` (`hunt.py:231-235`) is ownership-scoped
(`user_id` in the WHERE).

**Dedup integration.** `dedup.check_seen` (`services/dedup.py:28-86`) consults
BOTH `external_applications` and `explore_findings`, reporting
`{seen, applied, discarded, status, source, recommendation}` per URL
(`skip` when known). `record_application` (`dedup.py:89-186`) auto-links a
scouted finding by hash and flips it to the terminal `applied_external` state.

**MCP surface.** Tools `hunt_plan`, `source_playbook`, `list_sources`,
`submit_findings`, `check_seen`, `list_matches`, `get_match` plus the `/hunt`
prompt (`entrypoints/mcp/server.py:299-363`, `:674-690`).

## Design decisions

- **Profile/sector-pack-driven scoring** (AGENTS.md §1.5): mirror-image tests
  (nurse > software AND welder > nursing) prove no hardcoded persona survives.
- **Merge-on-re-sight, never overwrite**: the update only writes fields the new
  extraction actually carries, so a sparse re-sight cannot downgrade a rich
  finding (see Gotchas).
- **Dedup at ingest, not at display**: the `external_applications` gate runs
  before any scoring/insert, so an already-applied posting never re-enters the
  pipeline even as a row.
- **Caller commits** — services never commit; the MCP tool commits after a
  non-error result.

## Testing

- `tests/test_scoring.py` — mirror-image persona tests, remote/salary signals,
  empty-profile no-invention, 0-100 bound, `determine_action` thresholds
  (70/69/40/39), per-dimension isolation.
- `tests/test_hunt.py` (real tmp SQLite) — plan shape incl. `mode` per source;
  url_template query-fill proven on a US non-remote profile (the S2.6
  regression cover); ingest dedup via a tracking-param URL variant; re-sight
  merge (no downgrade) AND enrichment; already-hand-applied skip; non-http
  scheme skip; status/limit/min_score filters; cross-user invisibility;
  `check_seen` reports a scouted finding as `skip`/`source=finding`.
- `tests/test_hunt_rls_live.py` (`-m live`) — Postgres RLS arm; the fail-closed
  `external_applications` test still passes after the v4 table-recreate.
- Migration v4 recreate data-preservation (S2 gate fix):
  `tests/test_migrations.py:36` builds a v3 DB by hand, seeds a row, applies
  only the v4 recreate, and asserts every column + the new `finding_id` FK
  survive.
- Demo gate (S2.4): a non-tech (Registered Nurse) `/hunt` run plans → ingests
  → dedups a tracking-param variant → scores → lists.

## Gotchas

- **Re-sight downgrade bug** (caught in the S2.4 demo smoke, not by tests): a
  sparse re-sight overwrote the richer score. Fixed with the merge +
  re-score; two regression tests (`test_hunt.py:113-164`) pin both directions
  (sparse doesn't downgrade, richer enriches).
- **The `external_applications` dedup gate shipped untested** (gate P1) — a
  removal mutant passed the suite. Now pinned by
  `test_submit_findings_skips_a_url_already_hand_applied`.
- **SQLite table-recreate migrations are data-loss-prone**: v4's recreate of
  `external_applications` was never exercised with rows until the gate
  demanded a preservation test.
- **`check_seen`'s `discarded` field** is populated by `discard_match` (S3.4);
  it shipped in S2.4 for shape stability before its consumer existed.
- **The S2.6 `search_box` conversion silently removed the only end-to-end
  coverage of url_template query-fill** (test-auditor P1): the remote boards
  that exercised it became `search_box`. The US-profile test now kills that
  mutant — when a shared fixture changes mode, check what coverage it carried.
