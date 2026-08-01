# Database — port, dual-dialect adapter, migrations, RLS

> The persistence foundation: the `UnitOfWork` port, one adapter class serving
> SQLite (self-host default) and Postgres (hosted), hand-parallel migration
> runners for both dialects, and fail-closed row-level-security tenant
> isolation on Postgres. Built by S1.2 (Postgres + RLS + parity matrix) on
> S1.1 (port + SQLite adapter + migration runner) — both ported from
> startup-jobs-radar's battle-tested raw-SQL layer.

## How it works

**Port.** `src/mcpforwork/ports/db.py:22` — the `UnitOfWork` Protocol:
`execute` / `fetchone` / `fetchall` / `insert` / `set_user_context` /
`commit` / `rollback` / `close`, plus `is_postgres`. Rows are plain `dict` on
both backends, so service code never branches on the dialect. Services take
`(uow, user_id, ...)`; the caller owns the transaction.

**Adapter.** `src/mcpforwork/adapters/db/backend.py`:
- `connect(url, *, run_migrations=True)` (:129) picks the dialect by URL
  prefix (`sqlite:///`, `postgres://`/`postgresql://`; a bare path is SQLite)
  and runs migrations by default (self-host ergonomics).
- `SqlUnitOfWork` (:64) is the single class for both dialects; `?`
  placeholders are rewritten to `%s` for Postgres (:79-80).
- `insert()` (:96-101) returns the new id uniformly: SQLite `lastrowid`;
  Postgres appends `RETURNING id` (the surrogate key must be named `id`).
- psycopg v3 is lazy-imported with a clear error message (:55-61) —
  SQLite-only installs never load it.
- `set_user_context(user_id)` (:103-117) binds the tenant for RLS via
  session-scoped `set_config('app.current_user_id', …, false)`; a no-op on
  SQLite, where isolation is the app-level `WHERE user_id` filter.
- SQLite connections set `row_factory`, `PRAGMA foreign_keys=ON`,
  `busy_timeout=30000` (:44-52).

**Migrations.** `src/mcpforwork/adapters/db/migrations.py`:
- SQLite: `migrate_sqlite` (:275) walks `PRAGMA user_version` over the inline
  `MIGRATIONS` dict (:209); v1 is the base `schema.sql` (`users`,
  `audit_log`). `SCHEMA_VERSION` (:32) is the current head. Table-recreation
  scripts are listed in `_FK_RECREATE_MIGRATIONS` (:255 — empty today) to
  toggle FK enforcement around the script (:291-306).
- Postgres: `migrate_postgres` (:312) applies ordered `pg/*.sql` files and
  tracks versions in `schema_migrations`; every file is idempotent
  (`IF NOT EXISTS` / `ON CONFLICT DO NOTHING`). `_pg_statements` (:344) is a
  dollar-quote-aware statement splitter (psycopg has no `executescript`).
- The two dialect representations are authored separately and kept parallel
  by hand; the parity tests catch behavioral divergence.

**RLS (Postgres only).** `pg/001_initial.sql:18-22` provisions the
non-superuser `app` role (`NOINHERIT`, dev/test password — production must
`ALTER ROLE`). `users` and `audit_log` are pre-auth / cross-cutting and NOT
force-RLS'd. Each per-user table's migration then runs
`ENABLE + FORCE ROW LEVEL SECURITY` with the policy
`USING / WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::bigint)`
(e.g. `pg/002_profiles.sql:71-90`). `NULLIF(…)` yields NULL on an unset GUC,
so an unbound session matches zero rows — fail-closed. Hosted per-request
connections authenticate as `app` with `run_migrations=False` (the role
cannot run DDL; migrations are an admin/deploy step).

## Design decisions

- **psycopg is an optional `postgres` extra** (pyproject.toml:22-25) so the
  SQLite self-host stays driver-free — the SQLite/Postgres split IS the
  open-core split.
- **`insert()` replaced the donor's SQLite-only `last_insert_id(cur)`** when
  the second backend landed (S1.2) — one way to get a new id on both
  dialects.
- **Session-scoped `set_config`, NOT `SET LOCAL`** (:103-112): services
  commit mid-flow and keep querying on the same per-request connection; a
  transaction-scoped GUC would reset after the first commit and fail closed
  for the rest of the request. The function form is used because a bare `SET`
  cannot bind a placeholder.
- **RLS policy inline per table** — the static-SQL runner has no code seam to
  share; instead each real per-user table re-proves isolation in its own live
  test (S1.2 improvements).
- **`conn` (virgin) and `uow` (migrated) are separate fixtures** — migration
  tests need an un-migrated database, so folding `migrate()` into `conn`
  would have broken them (S1.1 improvements).

## Testing

- `tests/test_db_backend.py` — SQLite UoW behavior: dict rows, insert id,
  rollback discards writes, real-file backing, `set_user_context` no-op.
- `tests/test_migrations.py` — fresh migrate to `SCHEMA_VERSION`; re-run is a
  no-op; the v4 recreate preserves `external_applications` rows and adds the
  `finding_id` FK; the FK-recreate pattern rebuilds a parent with FK children
  intact and restores enforcement after.
- `tests/test_backend_parity.py` — the `any_uow` matrix: insert/read round
  trip, `?`→`%s` adaptation, FK join on both backends.
- `tests/test_pg_backend_live.py` (live) — dialect routing, idempotent PG
  migrations, `RETURNING id`.
- `tests/test_rls_live.py` (live) — the RLS mechanism on a probe table as the
  `app` role: each tenant sees only its rows, unset context sees nothing,
  `WITH CHECK` blocks cross-tenant writes. Real tables re-verify in
  `test_profiles_rls_live.py`, `test_dedup_rls_live.py`, and the later
  per-table live files.
- Live arm: `TEST_POSTGRES_URL=<superuser URL> uv run pytest -m live` against
  a local Docker Postgres; `tests/pg_support.py` derives the `app`-role URL
  and connects with `run_migrations=False`.

## Gotchas

- **psycopg has no `executescript`** — a naive `split(';')` breaks the
  `DO $$ … $$` block that provisions the app role; `_pg_statements` respects
  dollar quotes and copies `--` comments verbatim so a `$$` or `;` inside a
  comment is not interpreted (:344-351).
- **`PRAGMA foreign_keys` is a no-op inside an open transaction** — the
  FK-recreate helper commits first, toggles the PRAGMA around the script, and
  restores it in a `finally` (:298-306).
- **A failed `SELECT … FROM schema_migrations` poisons the PG transaction** —
  `_applied_pg_versions` rolls back before returning an empty set (:332-341).
- **`_FK_RECREATE_MIGRATIONS` is empty today**: the v4 recreate of
  `external_applications` needed no toggle because the table has no FK
  children (migrations.py:115-120). Register versions here when recreating a
  referenced parent.
- **The `app` role password in `pg/001_initial.sql` is a dev/test default** —
  production deployments MUST override it (`ALTER ROLE app PASSWORD …`).
