# Autopilot — consent artifacts (L1 approval + L2 policy)

> `services/autopilot.py` is THE write side of consent (ADR 0005, §9 P0):
> L1 approvals and L2 policies are written exclusively here, behind the
> human-session HTTP API — never by the MCP entrypoint, so no sequence of
> agent tool calls (possibly prompt-injected by posting content) can mint
> consent. Reads live in `services/apply.py`, which evaluates the artifacts
> inside `request_submit` (see `modules/apply.md` for the gate itself).
> Cards (latest first): S7.2c (pack `auto_apply_safe` curation — honest
> empty allowlist), S7.2b (L2 policy + queue), S7.2a (L1 approval).

## How it works

**L1 approval** — `approve_submit(uow, user_id, application_id, via)`
(`autopilot.py:31`): state-guarded to `awaiting_human|submit_requested`
(`_APPROVABLE_STATES`, :23 — the dashboard's "awaiting you" stage, so human
and agent never race); writes `submit_approved_at/via` on the application
row; re-approve is idempotent (`already_approved`); audited.

**L2 policy** (`autopilot.py:67-233`):

- **Schema** — migration 11 (`adapters/db/migrations.py:262-273`,
  `SCHEMA_VERSION` :32; PG twin `adapters/db/pg/011_autopilot_policy.sql`):
  `autopilot_policy(id, user_id, enabled, min_score, max_per_day,
  created_at, revoked_at)`, indexed on `user_id`. PG: BIGSERIAL/BOOLEAN/
  TIMESTAMP, FORCE RLS with the standard `app.current_user_id` policy.
- **Append-only.** `put_policy` (:72) revokes the prior active row and
  inserts the new one in the same transaction — at most one policy is
  active and every change survives for the audit trail. Active = newest
  row with `revoked_at IS NULL` (`get_policy`, :117). Both writes are
  audited (`put_autopilot_policy` / `revoke_autopilot_policy`).
- **Validation** (:78-97): `min_score` 0–100, `max_per_day` 1–50
  (`_MIN_SCORE_RANGE`/`_MAX_PER_DAY_RANGE`, :27-28 — a cap above 50/day is
  spam, not autopilot; a 0-cap policy would authorize nothing). JSON
  booleans are explicitly rejected as integers (`isinstance(True, int)` is
  True in Python — SQLite would silently store 1, psycopg would 500
  against the INT column). `enabled` is bound as a real bool: psycopg
  needs it for the BOOLEAN column, sqlite3 adapts `True` → 1.
- **`revoke_policy`** (:127) sets `revoked_at` (the row stays as history);
  new `request_submit` calls fall back to `await_human`. Already-minted
  authorizations are NOT recalled — an agent mid-submit on one is never
  stranded. No active policy → `not_found` error kind.
- **`evaluate(policy, score, source_slug, safe_sources, authorized_today)`**
  (:151) — the PURE L2 decision: authorize only when every criterion holds
  (active policy → source `auto_apply_safe` → score ≥ min → cap not
  reached). Returns `{authorize, reason, snapshot}`; the snapshot
  `{policy_id, score, source_slug, cap_used}` is what the authorization
  audit row carries — the record proves WHICH policy/score/source/cap
  state produced the decision. On authorize, `cap_used` counts THIS
  authorization in.
- **`queue(uow, user_id)`** (:184) — the L2 work queue, a QUERY not a
  table: approved findings on safe sources scoring at/above the policy
  min, with no open application (`NOT EXISTS` over
  draft/filling/awaiting_human/submit_requested), dedup-blocked postings
  filtered against `external_applications` hashes, ordered score DESC.
  Shared by the MCP tool and the dashboard. No policy → `{policy: None,
  items: []}`; no safe sources → policy plus honestly empty items.
- **`safe_source_slugs()`** (:143) — slugs whose pack flags
  `apply_playbook.auto_apply_safe` (`packs/registry.load_sources`).
  Honestly EMPTY after the S7.2c browser pass (none of the five
  global-remote boards qualified — see `modules/packs.md`); the
  conservative default is the product's risk posture.

**CI consent-write gate** (`.github/workflows/ci.yml:43-57`): two greps
fail the build if a consent write appears outside this one file —
`SET submit_approved_at` (L1) and `INSERT INTO/UPDATE autopilot_policy`
(L2). Schema/migrations define the tables; they never write them.

## Design decisions

- **Write/read split by module** (ADR 0005): the MCP entrypoint imports
  this module for READS only (`get_policy`, `queue`); a structural test
  pins that the write function names never appear in `server.py`.
- **Append-only over in-place update**: the policy history is itself audit
  evidence ("what did the human authorize, since when, superseded by
  what"), and revocation needs no special delete path.
- **`evaluate` is pure with injectable `safe_sources`/`authorized_today`**
  (and `request_submit` takes injectable `now`/`safe_sources`): the
  decision matrix and the UTC cap boundary are tested without touching the
  packs registry or the clock (zero-mocks contract).
- **Cap counted from the audit log** (`apply.py:_l2_authorized_today`,
  :325): `audit_log.created_at` is immutable, so the count cannot be
  gamed by rewriting application rows; the `detail LIKE '%"level": 2%'`
  marker is a text pre-filter both dialects evaluate identically, and the
  JSON key+value shape keeps the marker unambiguous if a third consent
  level ever exists.
- **Guidance avoids the literal decision verb** (S7.2b improvements): the
  CI consent-verb grep fails on `submit_authorized` outside `services/`,
  so `guidance.py` says "the submit IS authorized" and lets the response's
  `instruction` field carry the per-decision directive — the grep keeps
  full strength.

## Testing

- `tests/test_autopilot_l2.py` (28 tests, real SQLite at `tmp_path`):
  policy CRUD + supersede-keeps-history + tenant scoping + audit writes;
  range validation incl. JSON-booleans-as-integers; the full `evaluate`
  decision matrix; queue filters (safe/approved/scoring/unblocked, honest
  empty states); `request_submit` under L2 — authorize, L1-wins-over-L2
  precedence (:301), refusals per criterion (not-safe :312, below-score
  :326, cap-hit :347), revoke-mid-batch (:409 — minted authorizations NOT
  recalled), exactly-once double-submit (:434), UTC cap boundary
  (:365 — injected `now`: 23:59 yesterday doesn't count, 00:00 today
  does), `browser_autopilot_l2` confirm channel (:453); API routes (401
  matrix, camelCase roundtrip, body validation, cross-tenant, boards);
  structural: MCP entrypoint never references the write functions (:589),
  MCP policy tools read-only and honest (:602).
- `tests/test_autopilot_l2_live.py` (`-m live`, Docker PG): FORCE-RLS
  isolation (Bob cannot read/revoke Alice's policy), the full L2 loop on
  the TIMESTAMP/BOOLEAN dialect (snapshot contents verified), revoke
  mid-batch on PG.
- `tests/test_consent_gate.py` — the L0/L1 structural pins are unchanged;
  the CI grep extension covers the L2 writes (all three consent greps
  verified CLEAN locally on the card).
- Gate dispositions (S7.2b card): the atomic `AND consent_level = 0`
  guard's mutant survives the sequential suite — ACCEPTED as defense in
  depth for concurrent transactions (same pattern L1 ships). Cap
  count+flip TOCTOU under parallel `request_submit` — CLOSED by S7.2d
  (per-user `UPDATE users SET id = id` before the cap count; deterministic
  concurrency suite in `tests/test_apply_l2_concurrency.py` — see
  `modules/apply.md`).

## Gotchas

- **Revocation is not retroactive** — by design: a minted L2 authorization
  survives policy revocation (and re-entry at `consent_level == 2` skips
  the cap re-check, `apply.py:404-407`), so an agent is never stranded
  mid-submit. The dashboard's revoke copy says this honestly (W6.3).
- **The queue is only as honest as the packs**: no shipped pack is
  `auto_apply_safe` (S7.2c verified five boards and flagged none), so both
  adapters return empty items — pinned by
  `test_queue_defaults_to_empty_when_no_shipped_pack_is_flagged` (:262),
  the boards route test, and the packs allowlist guard (`frozenset()`).
  A future curation card must record browser evidence before any slug
  enters the allowlist.
- **PG "UTC day" inherits the server TZ** (pre-existing ADR 0001 shape;
  Docker/CI default is UTC): the SQLite cap window is pinned UTC by the
  injected-`now` test; live-PG cap-hit/midnight coverage against a real
  safe source waits until a future card flags one.
- **`put_policy` binds `enabled` as a Python bool** — binding 1/0 instead
  would work on SQLite and fail on psycopg's BOOLEAN column; the live arm
  is what guards this class.
- **GDPR**: `autopilot_policy` is in `privacy._USER_TABLES`
  (`services/privacy.py:28`) — export/delete coverage is mandatory for any
  new personal-data table (invariant §1.6); see `modules/privacy.md`.
