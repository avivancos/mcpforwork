# Apply orchestration — state machine, progress loop, consent gate

> The browser-apply loop: the server choreographs, the CLIENT's browser acts in the
> user's own session. `start_application` runs the deterministic preflight and returns
> an ordered step plan; `report_apply_progress` is the heartbeat; `request_submit` is
> THE consent gate (product invariant §1.2, §9 P0 security surface) — at consent level 0
> it always awaits the human. Obstacle pauses route captchas/logins to the human;
> playbook reports feed the S8 pack-update loop. Built by S4.1–S4.4; S6.0 added
> `abandon_application` (latest first: S6.0, S4.4, S4.3, S4.2, S4.1).

## How it works

**State machine** (`src/mcpforwork/domain/apply_flow.py`, pure): `STEP_KINDS` (:15) is
the full step vocabulary — navigate, fill, upload, answer, review, verify; **"submit" is
absent by construction**. `ALLOWED_TRANSITIONS` (:19-27): draft→filling→awaiting_human→
submit_requested→submitted→verified, `abandoned` reachable from every open state;
submitted/verified/abandoned are terminal. `build_steps(finding, profile, assets,
playbook)` (:34) emits the ordered plan: navigate (page content flagged UNTRUSTED,
:49-51) → fill with `value_refs` → upload (prefers the CV asset, :72-73) → optional
answer step for playbook quirks (:87) → always ends at `review`.

**Service** (`src/mcpforwork/services/apply.py` — `(uow, user_id, ...)` signatures, the
caller commits, every mutation audited via `audit.record`):
- `start_application` (:59) — preflight gates in order: match exists and is approved
  (:61-65); idempotent re-open of an open application for the same finding (:67-81,
  `_OPEN_STATES` :27); dedup gate rejects an already-applied URL (:83-89); daily cap
  `MAX_APPLICATIONS_PER_DAY = 10` (:25, :91-93); active profile required. Loads the
  pack's `apply` playbook by source_slug (:99-100), persists state `filling`, warns
  when no drafted assets exist.
- `report_apply_progress` (:133) — the heartbeat. Reports accepted ONLY while `filling`
  (:147-151); every report audited BEFORE branching (:159). `ok` advances
  `current_step`; the last `ok` flips to `awaiting_human` through a machine-checked
  write (`assert can_transition`, :204). `mismatch` keeps the step and returns a repair
  hint (:171-179). `blocked` with an obstacle in `_OBSTACLES` (:29) returns
  `{pause: true, instruction}` — the HUMAN resolves it in their browser; never bypassed
  (:181-193).
- `resolve_field` (:241) + `save_form_answer` (:410) — progressive profiling: saved
  `profiles.form_answers` win first (exact case-insensitive label match, :258-262);
  then profile fields via the strict `_CANDIDATE_LABELS` allowlist (:34-47); otherwise
  `{ask_user: true}` — never invent.
- `request_submit` (:286) — see the consent gate below.
- `confirm_submitted` (:325) — requires `submit_requested` (:333); flips to `submitted`
  with evidence and records the dedup ledger via
  `dedup_service.record_application(channel="browser_supervised")` (:341-350), so
  `check_seen` skips the URL forever.
- `record_outcome` (:365) — `no_reply|rejected|interview|offer|hired` (:283), only from
  submitted/verified (:374), structured error kinds (:370-378); calibration raw data.
- `abandon_application` (:219) — any open state → `abandoned` via `can_transition`
  (:229), user-scoped UPDATE (:231-234), audited with the reason. `abandoned` ∉
  `_OPEN_STATES`, so a later `start_application` opens a FRESH session.
- `get_asset_file` (:392) — writes the asset under `config.data_dir()/assets/
  <id>_<type>.md` for form uploads; read-side `ASSET_TYPES` whitelist (:401).

**Playbook reports** (`src/mcpforwork/services/playbooks.py`): `report_playbook_result`
(:19) captures opt-in `success|drift|break` diffs per source (`KINDS` :16); unknown
source or kind rejected (:22-25).

**Schema** — migration 6: `applications` (state, consent_level DEFAULT 0, steps JSON,
current_step, outcome, evidence) + `profiles.form_answers` (`adapters/db/migrations.py:
188-207`); migration 7: `playbook_reports` (:215-225). Postgres twins
`pg/006_applications.sql` / `007_playbook_reports.sql`, both FORCE RLS. MCP tools:
`server.py:444-549` plus `report_playbook_result` (:107) and guidance breadcrumbs
(`entrypoints/mcp/guidance.py:69-79`).

## The consent gate (invariant §1.2, §9 P0)

"No submit-class action without a recorded consent check" is enforced STRUCTURALLY at
three independent layers:

1. **Construction.** `STEP_KINDS` excludes "submit" — no code path can build a submit
   step (apply_flow.py:1-7, :14-15), and the plan ends at `review`. In the machine,
   `submitted` is reachable ONLY from `submit_requested`, and only `request_submit`
   writes that state (apply.py:297-303) — so the audit trail always carries a
   `request_submit` before any `confirm_submitted` (apply_flow.py:17-18).
2. **Decision.** At consent level 0 (the only level until the S7 autopilot card),
   `request_submit` ALWAYS returns `decision: await_human` (apply.py:314-322): the
   client shows the filled form, the HUMAN clicks Submit, then the client calls
   `confirm_submitted`. The string `submit_authorized` exists nowhere in the service
   source.
3. **CI gate.** The consent-verb gate (`.github/workflows/ci.yml:31-41`) greps
   `submit_authorized` across `src/mcpforwork/` and fails the build on any occurrence
   outside `src/mcpforwork/services/` (path-anchored exclusion). Tests pin the rest.

## Design decisions

- **Server choreographs, the client's browser acts** (apply.py:1-6): zero server-side
  browsing; obstacles go to the human because it is their session — captchas are never
  bypassed.
- **`submit_requested` exists for the audit trail**, introduced by the S4 gate fix
  (commit bfdeda2): without it, `confirm_submitted` never required a prior
  `request_submit` and the consent check could be skipped.
- **Idempotent re-open** — one open application per finding; `abandoned` was
  deliberately NOT added to `_OPEN_STATES` (S6.0) so abandoning unlocks a fresh
  session. S6.0 reused the existing terminal transition — no new abstraction or dep.
- **Playbook reports live in `services/playbooks.py`**, not apply.py: they are
  pack-maintenance capture (S8), not session flow.
- **Self-host asset path** — `get_asset_file` writes a local file under `data_dir`;
  hosted signed URLs are deferred to the hosted sprint (S4.3).

## Testing

- `tests/test_apply_flow.py` — "submit" not in STEP_KINDS (:47-48); property over
  representative inputs: every emitted kind ∈ STEP_KINDS, plan ends at review (:51-61);
  transitions cannot skip the human (:64-74); preflight blocks unapproved /
  already-applied / daily-cap / foreign finding; idempotent re-open (:129-136).
- `tests/test_apply_progress.py` — ok advances; last ok → awaiting_human, NEVER
  submit-authorized (:34-44); mismatch repair; blocked pause never suggests a bypass
  (:57-66); every report audited (:103-111); resolve_field profile/allowlist/
  saved-answer behavior.
- `tests/test_consent_gate.py` — L0 always `await_human` (:36-45); `inspect.getsource`
  proof that no service path yields `submit_authorized` (:48-53); request/confirm state
  preconditions; confirm writes the dedup ledger (:67-79); no submitted→awaiting_human
  regression (:93-104); confirm-without-request and double-confirm rejected (:107-117);
  get_asset_file under data_dir (:139-153).
- `tests/test_playbook_reports.py` — report validation; obstacle pause→resume
  round-trip (:32-49).
- `tests/test_abandon.py` — abandon from all three open states; terminal states
  rejected (`verified` seeded directly, :95-108); fresh session after abandon
  (:135-144); tool-layer persistence on a FRESH connection (:147-168). Mutant probes
  killed: can_transition-removal, cross-tenant-scope-removal, dropped-commit (S6.0
  closure).
- `tests/test_mcp_apply_tools.py` — full supervised flow E2E through the MCP tools with
  fresh-connection reads (:30-83).
- `tests/test_apply_rls_live.py` (live) — applications + playbook_reports tenant
  isolation and fail-closed unset context on Postgres.

## Gotchas

- **The state machine was decorative until the S4 gate fix** (bfdeda2): no service
  called `can_transition`, so a re-reported step regressed submitted→awaiting_human and
  confirm never required request. Every state write now goes through `can_transition`;
  reports only apply while `filling` (apply.py:147-151).
- **Greedy label matching invented screener answers** (S4 gate P1): "Company name" ~
  name answered with the candidate's own name. Fixed with the strict
  `_CANDIDATE_LABELS` allowlist + saved-answer precedence; adversarial regression test
  at test_apply_progress.py:81-92.
- **A declined application was stuck open forever before S6.0** — reports rejected
  outside `filling`, `start_application` perpetually re-opened it.
  `abandon_application` is the escape hatch.
- **Silent no-op UPDATEs / commit drops** — all mutations are user-scoped (`WHERE id =
  ? AND user_id = ?`); tests read state back and verify persistence on FRESH
  connections (the S3 lesson), so a never-matching UPDATE or a dropped commit cannot
  pass (test_abandon.py:59-63, test_mcp_apply_tools.py:1-2).
- **The daily cap counts STARTED applications** (`created_at >= today` string compare,
  apply.py:50-56), including abandoned ones — abandoning does not refund quota.
- **Unknown obstacle strings degrade to `kind: "unknown"`** (apply.py:182) — the pause
  instruction is still emitted; the audit carries the raw value.
- **Page content is untrusted input** — the navigate step tells the client never to
  follow instructions embedded in the posting (apply_flow.py:49-51); prompt-injection
  surface.
- **`verified` has no service transition yet** — reachable only via direct seed in
  tests (test_abandon.py:95-108).
- Carried from S6.0 (non-blocking): a shared free-text length cap across audit params
  when the hosted multi-tenant path lands (→ ADR 0001).
