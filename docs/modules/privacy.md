# Privacy: GDPR export & erasure (export_my_data / delete_my_data)

> Data portability + erasure over the full per-user data model, plus the
> carried S1-gate requirement that every read over the non-RLS'd `audit_log`
> scopes by `user_id`. Cards (latest first): S7.2b (added `autopilot_policy`),
> S6.6c (added `sessions` to the inventory), S6.4.

## How it works

`src/mcpforwork/services/privacy.py` — one ordered `_USER_TABLES` constant
(`privacy.py:21-33`) drives BOTH export and delete so the two can never
drift. Order is FK-safe child -> parent (findings are parents of
applications/generated_assets/external_applications, so they come after those
children; `sessions`, `audit_log`, and `autopilot_policy` lead). `users` is
the root: scoped by `id`, exported first, deleted last.

- `export_user_data(uow, user_id)` (`privacy.py:41`): the `users` row plus
  `SELECT * … WHERE user_id ORDER BY id` per table. Read-only and
  JSON-serializable end to end.
- `delete_user_data(uow, user_id)` (`privacy.py:71`): `_erase_asset_files`
  FIRST (`privacy.py:52`, before the rows vanish — the filename derives from
  the generated_assets row: `data_dir/assets/<id>_<asset_type>.md`, scoped to
  the user's own rows so it is multi-tenant-safe, with a read-side
  `ASSET_TYPES` whitelist). Then DELETE per table over
  `(*_USER_TABLES, *_AUTH_TABLES)`, then the `users` row. Returns per-table
  counts + `asset_files_removed`; the caller commits.
- `_AUTH_TABLES` (`privacy.py:38`): `magic_link_tokens` — erased (FK to
  users) but NOT exported: a hash of a single-use credential is internal
  auth state, not user content the subject provided.
- Table names are interpolated into SQL — safe only because the list is
  trusted code-defined identifiers (SQL identifiers cannot be parameterized).
- **No post-delete audit row**: the user's audit_log is itself erased and the
  FK to a deleted user would fail — erasure leaves no trace, which is
  GDPR-correct for self-host.

**Tools** (`src/mcpforwork/entrypoints/mcp/server.py:617-636`):
`export_my_data()` is read-only; `delete_my_data(confirm)` refuses unless
`confirm=True` — an LLM client must never wipe the user's data by accident —
and the refusal names the guard. `next_action` strings at
`entrypoints/mcp/guidance.py:93-94`.

**audit_log scoping.** `audit_log` is deliberately NOT FORCE-RLS'd
(cross-cutting), so unlike the RLS-forced tables nothing automatic filters
it: the explicit `WHERE user_id` in export (and the API's `/v1/audit` route)
is the only thing keeping one tenant's applied URLs out of another's export.
Closing this read-scoping item marked ADR 0001 RESOLVED.

## Design decisions

- **Single inventory constant**: export and delete share `_USER_TABLES`, so a
  new table is either in both or visibly in neither.
- **confirm=True gate on the destructive tool**, not on export: read paths
  are safe for an LLM client to call freely; erasure is not.
- **INVARIANT (AGENTS.md §1.6): every new personal-data table MUST be added
  to `_USER_TABLES`** (and seeded in the export completeness test) — otherwise
  erasure silently orphans it and export silently drops it. `sessions`
  (S6.6c, migration 9) is the worked example.

## Testing

- `tests/test_privacy.py` (12 tests, real SQLite at `tmp_path`): `_populate`
  seeds a row in EVERY per-user table so the completeness assertions are
  real; no cross-user leak including audit-logged applied URLs; delete is
  FK-safe, leaves other users untouched, and is idempotent (second run = all
  zeros); on-disk asset files erased; nonexistent user is a no-op;
  magic_link_tokens erased (FK regression); tool refuses without confirm
  (verified on a fresh connection); tool roundtrip; registration pin.
- `tests/test_privacy_rls_live.py` (2 `@pytest.mark.live` tests, Docker PG):
  audit_log tenant isolation via the app role (where RLS does not help), and
  delete erases one tenant while the admin connection (RLS-bypassing) proves
  the other fully intact.
- S6.4 gate mutant probes (all killed): dropped WHERE on audit_log, reversed
  delete order, dropped commit.

## Gotchas

- `tests/test_privacy.py` `_PER_USER_TABLES` omits only `magic_link_tokens`
  (auth-internal, never exported). `sessions` and `autopilot_policy` joined the
  test set on S7.2b (the fused gate's P1: the new table needed export/delete
  coverage, and the pre-existing `sessions` gap was fixed in the same pass) —
  `_populate` seeds them via `autopilot.put_policy` and
  `auth_session.issue_session`. A table added to `_USER_TABLES` only joins the
  test set if `_populate` can seed a real row.
- `_erase_asset_files` must run BEFORE deleting `generated_assets` rows — the
  on-disk filename is derived from the row's `id` + `asset_type`; after the
  DELETE the mapping is unrecoverable.
- **Prompt-injection residual** (documented in ADR 0001): a malicious page
  could try to talk the client LLM into `delete_my_data(confirm=True)`.
  Accepted for self-host; a hosted/headless deployment needs out-of-band
  confirmation (P1 there) — do not weaken the confirm gate to "fix" UX.
- Erasure of a logged-in account dies its other sessions too: `_current_user`
  in the API rejects deleted-user cookies (S6.6c), so no orphaned session
  rows or cookie zombies survive the users-row DELETE.
