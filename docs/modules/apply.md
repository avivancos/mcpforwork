# Apply orchestration — state machine, progress loop, consent gate

> The browser-apply loop: the server choreographs, the CLIENT's browser acts in the
> user's own session. `start_application` runs the deterministic preflight;
> `report_apply_progress` is the heartbeat; `request_submit` is THE consent gate
> (invariant §1.2, §9 P0) — without a recorded consent artifact it always awaits the
> human; an L1 approval (S7.2a, ADR 0005) or an active L2 policy (S7.2b) turns a
> re-entry into a one-time `submit_authorized`. Latest first: S7.2b (L2 recorded
> policy — the write-side module is documented in `modules/autopilot.md`), W6.2
> (dashboard approval UI — the UI half of L1, documented in `modules/web.md`),
> S7.2a, S6.0, S4.4–S4.1.

## How it works

**State machine** (`domain/apply_flow.py`, pure): `STEP_KINDS` (:15) is the full step
vocabulary — navigate, fill, upload, answer, review, verify; **"submit" is absent by
construction** and never gains entry (ADR 0005: authorization is a response-scoped
directive, never a persisted plan step). `ALLOWED_TRANSITIONS` (:19-27): draft→filling→
awaiting_human→submit_requested→submitted→verified, `abandoned` from every open state;
submitted/verified/abandoned terminal. `build_steps` (:34) emits the plan: navigate
(page content flagged UNTRUSTED, :49-51) → fill → upload → optional answer → `review`.

**Service** (`services/apply.py` — `(uow, user_id, ...)`; the caller commits; every
mutation audited via `audit.record`):
- `start_application` (:59) — preflight: match approved (:61-65); idempotent re-open
  per finding (:67-81, `_OPEN_STATES` :27); dedup gate (:83-89); daily cap 10/day
  (:25, :91-93); active profile. Loads the pack playbook, persists `filling`.
- `report_apply_progress` (:133) — the heartbeat: reports accepted ONLY while `filling`
  (:147-151), audited BEFORE branching (:159); `ok` advances, last `ok` flips to
  `awaiting_human` via `assert can_transition` (:204); `mismatch` returns a repair
  hint; `blocked` on `_OBSTACLES` (:29) pauses to the HUMAN — never bypassed (:181-193).
- `resolve_field` (:241) + `save_form_answer` (:535) — progressive profiling: saved
  `form_answers` win first (:258-262), then the strict `_CANDIDATE_LABELS` allowlist
  (:34-47), else `{ask_user}` — never invent.
- `request_submit` (:372) / `confirm_submitted` (:447) — see below; confirm records
  the dedup ledger with channel per `consent_level` (0 `browser_supervised`,
  1 `browser_autopilot_l1`, 2 `browser_autopilot_l2`, :468).
- `record_outcome` (:490), `abandon_application` (:219, any open state → `abandoned`,
  ∉ `_OPEN_STATES` so a later start opens FRESH), `get_asset_file` (:517).

**Playbook reports** (`services/playbooks.py:19`) capture opt-in `success|drift|break`
diffs per source for the S8 pack-update loop.

**Schema** — migration 6: `applications` + `profiles.form_answers`; 7:
`playbook_reports`; 10 (S7.2a): `applications.submit_approved_at` /
`submit_approved_via` (`adapters/db/migrations.py:254-257`; PG twin
`pg/010_applications_submit_approval.sql` — TIMESTAMP, idempotent; the table is FORCE
RLS since 006, so the new columns inherit tenant isolation).

## The consent gate (invariant §1.2, §9 P0)

"Never submit without a recorded consent check" is enforced STRUCTURALLY:

1. **Construction.** `STEP_KINDS` excludes "submit"; the plan ends at `review`.
   `submitted` is reachable ONLY from `submit_requested`, which only `request_submit`
   writes (apply.py:396-401) — the audit always carries request before confirm.
2. **Decision.** `request_submit` (:372) is the only place a submit directive can be
   issued, in a fixed order (:402-423): L1 approval (`submit_approved_at` set →
   `_authorize_l1`) → already-L2 re-entry (`consent_level == 2` re-returns the
   directive WITHOUT a cap re-check — a minted authorization is never stranded)
   → L2 policy (`autopilot.evaluate` over the active policy) → else `await_human`
   (:435-444; the response's `reason` field names the failed L2 criterion). The
   client shows the form, the HUMAN clicks Submit at L0, then calls
   `confirm_submitted`. `submit_authorized` lives only inside `services/`.
3. **CI gates** (`.github/workflows/ci.yml`): consent-verb gate (:31-41) fails on
   `submit_authorized` outside `src/mcpforwork/services/`; consent-write gate
   (:43-57, ADR 0005) fails on `SET submit_approved_at` OR
   `INSERT INTO/UPDATE autopilot_policy` outside `services/autopilot.py`.
   Inspect-source tests pin the rest.

## The L1 approval loop (S7.2a, ADR 0005)

Consent artifacts are written ONLY by the human-session HTTP API, never by the MCP
entrypoint: MCP tools are invoked by the client LLM on untrusted posting content, so
an agent-reachable consent write would let a prompt-injected agent mint its own
consent. The loop:

1. `POST /v1/applications/{id}/approve-submit` (`entrypoints/api/app.py:360-376`,
   route :563) — session-auth (magic-link cookie), 404 cross-tenant, structured error
   kinds (S6.10). The ONLY L1 consent-write surface; MCP has no equivalent tool.
   The dashboard's "Approve submit" button (W6.2 — see `modules/web.md`) is the
   human-facing surface of this route.
2. `autopilot.approve_submit` writes the artifact — state-guarded, idempotent,
   audited (the write side is documented in `modules/autopilot.md`).
3. `request_submit` re-entry — `submit_requested` re-evaluates instead of erroring
   (:393): approval set → `_authorize_l1`; none → `await_human` (unchanged L0).
4. `_authorize_l1` (:286) — exactly-once via the ATOMIC `consent_level` 0→1 flip:
   `UPDATE ... WHERE consent_level = 0` (:301-305), the `submit_authorized` audit row
   (snapshotting `approved_at`/`approved_via`) written only on rowcount 1 (:306-317).
   A retried `request_submit` re-returns the directive without a second audit row —
   crash-safe idempotency; a crashed client is never stranded.
5. `confirm_submitted` records channel `browser_autopilot_l1` (:468).

## The L2 policy branch (S7.2b, ADR 0005)

The human records an autopilot policy (min score, UTC daily cap) via the
human-session API — the write-side module is `services/autopilot.py`, documented
in `modules/autopilot.md`. The gate side here:

1. **Evaluation** (:409-423) — with an active policy, the match's score and
   `source_slug` feed `autopilot.evaluate` together with
   `safe_sources` (injectable; defaults to `autopilot.safe_source_slugs()`) and
   `_l2_authorized_today` (:325) — authorizations minted in the current UTC
   CALENDAR day, counted from the audit log's immutable `created_at` with a
   `detail LIKE '%"level": 2%'` text pre-filter both dialects evaluate
   identically (ADR 0001 follow-up, now load-bearing: the day boundary is UTC).
2. **Authorization** — `_authorize_l2` (:339) mirrors the L1 exactly-once
   pattern: the ATOMIC `consent_level` 0→2 flip (`UPDATE ... WHERE
   consent_level = 0`, :352-357); only the transaction winning the flip writes
   the `submit_authorized` audit row carrying the criteria snapshot
   `{policy_id, score, source_slug, cap_used}` (:358-364). A retried
   `request_submit` re-returns the directive without a second audit row.
3. **Refusal** — a failed criterion falls through to `await_human` with
   `reason` naming it (not-safe / below-score / cap-reached); nothing is
   written but the usual `request_submit` audit row.
4. `confirm_submitted` records channel `browser_autopilot_l2` (:468).

## Design decisions

- **Server choreographs, the client's browser acts** (apply.py:1-6): zero server-side
  browsing; obstacles go to the human — it is their session.
- **ADR 0005** (`backlog/decisions/0005_consent_writes_api_only.md`): consent artifacts
  (L1 approval, L2 policy since S7.2b) are written exclusively behind the
  session-authenticated API; the L1 artifact lives on the application row and the L2
  policy is a per-user append-only table, so both inherit tenant isolation (RLS on PG,
  `user_id` scoping) and the audit snapshots the criteria at authorization time. The
  dashboard approves and records policy — it never fills or submits.
- **`submit_requested` exists for the audit trail** (S4 gate fix, bfdeda2); idempotent
  re-open keeps one open application per finding, with `abandoned` deliberately NOT in
  `_OPEN_STATES` (S6.0); playbook reports live in `services/playbooks.py` (pack
  maintenance, not session flow); self-host asset path defers hosted signed URLs (S4.3).

## Testing

- `tests/test_autopilot_l1.py` (14 tests) — approval write + state guard + cross-tenant
  blindness; double-approve idempotency (never re-mints); abandoned rejected; re-entry
  without approval still awaits; authorized exactly once (one audit row, retry-safe);
  approval BEFORE the first request_submit authorizes on first entry; L1 vs L0 confirm
  channels; the API route: 401 unauthenticated, happy path, cross-tenant 404, wrong
  state rejected.
- `tests/test_autopilot_l1_live.py` (live PG) — the full L1 loop on Postgres, tenant
  isolation included (TIMESTAMP dialect, RLS inherited from 006).
- `tests/test_autopilot_l2.py` (28 tests) — the L2 gate side: authorize under a
  policy; `test_l1_approval_wins_over_an_l2_policy` pins the decision order;
  one refusal test per criterion (not-safe source, below-score, cap-hit);
  `test_utc_cap_window_resets_at_midnight` (injected `now`: 23:59 yesterday
  doesn't count, 00:00 today does); revoke-mid-batch stops NEW authorizations
  without recalling minted ones; `test_double_request_submit_l2_is_exactly_once`
  (one audit row, retry-safe); L2 confirm channel. The policy module's own
  coverage is enumerated in `modules/autopilot.md`.
- `tests/test_autopilot_l2_live.py` (live PG) — the L2 loop on the
  TIMESTAMP/BOOLEAN dialect, FORCE-RLS policy isolation, revoke mid-batch.
- `tests/test_consent_gate.py` — evolved on S7.2a: the written-to-die
  `test_no_source_path_yields_submit_authorized` was replaced by three stronger ones:
  no approval → every path awaits (:50); approval-write SQL lives only in
  `services/autopilot.py` (:61); the MCP entrypoint never references the approval write
  (:79). Plus L0 always `await_human` (:38), request/confirm preconditions, dedup
  ledger on confirm, no submitted→awaiting_human regression, double-confirm rejected.
- `tests/test_apply_flow.py` / `test_apply_progress.py` — "submit" ∉ STEP_KINDS; every
  emitted kind ∈ STEP_KINDS, plan ends at review; transitions cannot skip the human;
  preflight gates; idempotent re-open; ok advances, last ok → awaiting_human; mismatch
  repair; blocked pause never bypassed; resolve_field allowlist/saved-answer precedence.
- `tests/test_playbook_reports.py` / `test_abandon.py` / `test_mcp_apply_tools.py` —
  report validation, pause→resume round-trip; abandon from all open states, terminal
  rejected, fresh session after, fresh-connection persistence (S6.0 mutant probes:
  can_transition / tenant-scope / dropped-commit); supervised E2E via MCP tools.
- `tests/test_apply_rls_live.py` (live) — applications + playbook_reports tenant
  isolation, fail-closed unset context on Postgres.
- S7.2a mutant probes killed (observed): consent_level==0 guard removed → two
  authorization audit rows, test failed; tenant scope removed from the approve SELECT →
  both cross-tenant tests failed. Both reverted md5-verified.

## Gotchas

- **The state machine was decorative until the S4 gate fix** (bfdeda2): a re-reported
  step regressed submitted→awaiting_human. Every state write now goes through
  `can_transition`; reports only apply while `filling` (apply.py:147-151).
- **Greedy label matching invented screener answers** (S4 gate P1) — fixed with the
  strict `_CANDIDATE_LABELS` allowlist + saved-answer precedence.
- **A declined application was stuck open forever before S6.0** — abandon is the escape
  hatch; abandoning does not refund the daily cap (it counts STARTED applications,
  apply.py:50-56).
- **Silent no-op UPDATEs / commit drops** — all mutations are user-scoped; tests read
  state back on FRESH connections (the S3 lesson).
- **Page content is untrusted input** — the navigate step forbids following posting
  instructions (apply_flow.py:49-51); ADR 0005 applies the same model to consent.
- **`audit.record` serializes detail with `json.dumps(default=_iso)`**
  (services/audit.py:32) — S7.2a root-fix: a Postgres datetime inside a detail dict
  (the `submit_authorized` row's `approved_at`) crashed the write; normalized at the
  sink so no caller can hit it again.
- **`verified` has no service transition yet** — seed-only in tests. The authorized
  path writes no `request_submit` audit row: `submit_authorized` supersedes it (ADR 0005, P3).
- **L2 cap count+flip TOCTOU** (S7.2b P2, follow-up on S7.2d): under PARALLEL
  `request_submit` calls, N distinct pre-staged applications could each pass the
  cap check before any flip lands. Single-user self-host makes this unlikely but
  not impossible (a parallelizing client); S7.2d serializes count+flip. The
  atomic `AND consent_level = 0` guard is the same-shaped defense in depth L1
  ships — unobservable in the sequential suite (mutant survives, accepted).
- **A minted L2 authorization is never recalled** — re-entry at
  `consent_level == 2` re-returns the directive with no cap re-check
  (:404-407), and revoking the policy mid-batch stops only NEW authorizations.
  The alternative (recall on revoke) would strand an agent mid-submit.
