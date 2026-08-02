# Privacy: GDPR export & erasure (export_my_data / delete_my_data)

> Data portability + erasure over the full per-user data model, plus the
> carried S1-gate requirement that every read over the non-RLS'd `audit_log`
> scopes by `user_id`. Cards (latest first): S7.2d (MCP `delete_my_data`
> two-step + `delete_confirm_tokens`), S7.2b (`autopilot_policy` in the
> inventory), S6.6c (`sessions`), S6.4.

## How it works

`src/mcpforwork/services/privacy.py` — one ordered `_USER_TABLES` constant
(`privacy.py:25-37`) drives BOTH export and delete so the two can never
drift. Order is FK-safe child → parent (findings are parents of
applications/generated_assets/external_applications, so they come after those
children; `sessions`, `audit_log`, and `autopilot_policy` lead). `users` is
the root: scoped by `id`, exported first, deleted last.

- `export_user_data(uow, user_id)` (`privacy.py:117`): the `users` row plus
  `SELECT * … WHERE user_id ORDER BY id` per table. Read-only and
  JSON-serializable end to end.
- `delete_user_data(uow, user_id)` (`privacy.py:147`): `_erase_asset_files`
  FIRST (`privacy.py:128`, before the rows vanish — filename
  `data_dir/assets/<id>_<asset_type>.md`, scoped to the user's own rows,
  `ASSET_TYPES` whitelist). Then DELETE per table over
  `(*_USER_TABLES, *_AUTH_TABLES)`, then the `users` row. Returns per-table
  counts + `asset_files_removed`; the caller commits.
- `_AUTH_TABLES` (`privacy.py:43`): `magic_link_tokens` +
  `delete_confirm_tokens` — erased (FK to users) but NOT exported: hashes of
  single-use credentials are internal auth state, not subject content.
- Table names are interpolated into SQL — safe only because the list is
  trusted code-defined identifiers (SQL identifiers cannot be parameterized).

### Two-step MCP erasure (S7.2d)

The agent-reachable path is no longer a bare boolean:

1. **`request_deletion`** (`privacy.py:56`) — counts every table in
   `(*_USER_TABLES, *_AUTH_TABLES)` plus `users`, mints a raw
   `secrets.token_urlsafe(32)` confirm token (only the sha256 hash stored),
   audits `delete_my_data_requested`, returns `{summary, confirm_token,
   expires_in_seconds}` (`CONFIRM_TOKEN_TTL_SECONDS = 300`, :46).
2. **`execute_deletion`** (`privacy.py:82`) — redeems by hash. Unknown and
   cross-tenant collapse to one `invalid_token` refusal (no existence leak).
   Used / expired / concurrent-loser (`UPDATE … AND used_at IS NULL` with
   `rowcount != 1`) refuse and delete NOTHING. On success: audit
   `delete_my_data_confirmed` **BEFORE** `delete_user_data` (the erase wipes
   `audit_log`; a crash mid-erase still leaves the consent trace in the
   transaction log), then erase.

**MCP tool** (`entrypoints/mcp/server.py:626-642`):
`delete_my_data(confirm_token: str = "")` — empty → `request_deletion`;
non-empty → `execute_deletion`. The `confirm` boolean is GONE (structural
test: `confirm=True` raises `TypeError`). Breadcrumb at
`guidance.py:94-98`.

**Schema** — migration 12 (`adapters/db/migrations.py:279-288`,
`SCHEMA_VERSION` :32; PG twin `pg/012_delete_confirm_tokens.sql`): dedicated
`delete_confirm_tokens(user_id, token_hash UNIQUE, expires_at, used_at)` —
epoch seconds, same pattern as magic-link tokens. PG: FORCE RLS (unlike
`magic_link_tokens`); cross-tenant redeem sees no row; the service
`user_id` check is defense in depth.

**API `/v1/account/delete`** still calls `delete_user_data` directly
(`entrypoints/api/app.py:607-617`): the dashboard is a human session behind
typed confirmation — that IS the two-step equivalent for a human. The token
flow guards only the agent-reachable MCP path.

## Design decisions

- **Single inventory constant**: export and delete share `_USER_TABLES`.
- **Dedicated token table, not `magic_link_tokens`**: mixing kinds would let
  a login token replay as a delete confirmation (and vice versa).
- **Two-step is friction, not ADR-0005 provenance** (S7.2d P2-2): the
  confirm_token is returned in the MCP response (into agent context); a
  prompt-injected agent could still chain step 1 → 2. It kills the
  bare-boolean P0 (threading a server-minted, single-use, 5-min value across
  two audited calls) but is NOT a human-session-bound consent artifact.
  Follow-up candidate: dashboard-minted delete confirmations on the hosted
  track.
- **INVARIANT (AGENTS.md §1.6): every new personal-data table MUST be added
  to `_USER_TABLES`** (and seeded in the export completeness test).

## Testing

- `tests/test_privacy.py` (20 tests, real SQLite at `tmp_path`): inventory
  completeness; no cross-user leak; FK-safe / idempotent delete; asset
  files; magic_link erase; two-step lifecycle — mint-without-delete,
  valid redeem, unknown / reused / expired / TTL-boundary (`>=` → expired
  at exactly `expires_at`) / cross-tenant refusal; own token rows erased;
  MCP two-step roundtrip; **no boolean confirm path**.
- `tests/test_privacy_rls_live.py` (live PG): audit_log isolation; delete
  one tenant / spare the other; **`delete_confirm_tokens` RLS-invisible
  across tenants**.
- Mutant probes (S7.2d): (c) cross-tenant check removed → KILLED; (b)
  `AND used_at IS NULL` removed → SURVIVED (written rejection: every
  successful mark is followed by erase of the token row in the SAME
  transaction, so a concurrent loser's UPDATE matches 0 rows via
  `rowcount != 1` anyway; guard kept as defense in depth).

## Gotchas

- `_AUTH_TABLES` (tokens) are counted in the deletion **summary** and erased,
  but never appear in the export payload — do not "fix" that gap by
  exporting hashes.
- `_erase_asset_files` must run BEFORE deleting `generated_assets` rows.
- **Prompt-injection residual** (ADR 0001 / S7.2d P2-2): chaining the two
  MCP calls without a human is still possible; do not weaken further to
  "confirm" UX. The dashboard typed-DELETE path remains the human-bound
  equivalent.
- Erasure of a logged-in account dies its other sessions too (`_current_user`
  rejects deleted-user cookies, S6.6c).
