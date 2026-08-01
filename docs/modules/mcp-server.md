# MCP server (stdio entrypoint)

> The product's primary interface: a FastMCP server over stdio that a self-host
> client (Claude Code / Desktop) connects to with zero account. Thin wiring
> only — each tool opens a tenant-scoped UnitOfWork, calls a service, and
> returns JSON with a `next_action` breadcrumb. Built by S2.1; later shaped by
> S3.x/S4.x tools, the S4.4 `_tenant_uow` simplifier, S6.5 guidance, and the
> S6.8 tenant alignment (ADR 0006).

## How it works

**Server.** One module-level `mcp = FastMCP("mcpforwork", instructions=SERVER_INSTRUCTIONS)`
(`src/mcpforwork/entrypoints/mcp/server.py:41`). 38 `@mcp.tool()` functions
return `json.dumps(...)` strings; 4 `@mcp.prompt` functions (`/setup`,
`/review`, `/apply`, `/hunt`, `server.py:613-690`) are the client behavioral
contracts. `main()` runs `mcp.run(transport=os.environ.get("MCPFORWORK_TRANSPORT",
"stdio"))` (`server.py:693`); console script `mcpforwork-mcp`
(`pyproject.toml:39`), dependency `mcp>=1.2` (`pyproject.toml:10`).

**Per-call tenant seam.** `_uow()` (`server.py:83-92`): `connect(config.db_url())`
→ `_resolve_local_user` → `set_user_context` → return `(uow, user_id)`; on any
setup failure the connection is closed before re-raise (no leak). Most tools use
the `_tenant_uow()` context manager (`server.py:95-103`), the S4.4 simplifier
over repeated try/finally. `_resolve_local_user` (`server.py:50-80`) keys the
self-host tenant by EMAIL (`MCPFORWORK_USER_EMAIL`, default `local@self-host`)
so dashboard magic-link login lands on the SAME users row the MCP writes as
(S6.8, ADR 0006); `MCPFORWORK_USER_ID` remains as an explicit pin, and pin +
conflicting email fails loud instead of silently splitting the tenant.

**Response envelope.** `_ok(tool, payload)` (`server.py:135-137`) injects
`next_action` from `guidance.next_action(tool)` and serializes with
`default=_json_default` (`server.py:122-128`) — datetime/date → ISO-8601, so
payloads are dialect-neutral (Postgres TIMESTAMPs deserialize to `datetime`;
SQLite returns strings). Errors are `{"error": msg}` via `_fail`
(`server.py:131-132`); services return error dicts, tools never raise.

**Handshake.** `server_info` (`server.py:145-162`) returns
`{name, version, tools, invariants, next_action}` — version from
`importlib.metadata`, tools from `mcp._tool_manager`, invariants from the
`INVARIANTS` constant (`server.py:43-47`).

**Guidance module.** `entrypoints/mcp/guidance.py` is dependency-free by
import-linter contract (`pyproject.toml:123-134`): `SERVER_INSTRUCTIONS`
(`guidance.py:11-31`) is the server-level prompt; `next_action(tool)`
(`guidance.py:99-101`) reads a static dict. Full coverage: `docs/guidance.md`.

**Config.** `src/mcpforwork/config.py` is resolved on every call (never
cached): `db_url()` (`config.py:21-27`, env `MCPFORWORK_DB_URL`, default
`sqlite:///<data_dir>/mcpforwork.db`), `local_user_id()` (`config.py:33-42`),
`local_user_email()` (`config.py:45-50`).

## Design decisions

- **Thin by contract.** No business logic in tools; services own consent, caps,
  dedup. Entrypoint-independence lint contracts arrived only once a second
  entrypoint existed (rule of two, ADR 0001) — now `pyproject.toml:103-121`.
- **JSON strings, not structured content.** Tools return `json.dumps` so the
  envelope (`next_action`, `error`) is uniform and testable without a client.
- **Email-keyed tenant (S6.8)** replaced the S2.1 id-keyed seed
  (`MCPFORWORK_USER_ID` default 1) so MCP and dashboard share one users row;
  the pin survives as an escape hatch with a contradiction check.
- **`_json_default` at the serialization boundary** (not per-service) — one
  seam handles the PG/SQLite type skew for every present and future tool.

## Testing

- `tests/test_mcp_server.py` — real in-memory FastMCP (`asyncio.run`, zero
  mocks): tool registration, `server_info` payload, **every registered tool has
  a `next_action` breadcrumb** (`:23-26`), instructions state the invariants
  and the shipped apply loop (no "later sprint" claims), `_uow` seeds the local
  user idempotently.
- `tests/test_mcp_server_live.py` (`-m live`) — drives the tools against real
  Postgres and asserts TIMESTAMP columns serialize (`:35-47`); guards the
  `_json_default` fix.
- `tests/test_mcp_asset_tools.py` — full apply flow through the tools on a tmp
  DB, persistence proven on a FRESH connection; prompts may only reference
  registered tools (`:97-109`).
- Fixtures: `uow` (real tmp SQLite) and `mcp_env` (env-pointed `_uow`) in
  `tests/conftest.py:39-56`.

## Gotchas

- **SQLite hides PG datetime crashes** (S2.1 gate P1): the all-TEXT SQLite path
  serialized fine while Postgres tools crashed on `datetime` — fixed by
  `_json_default`; the live-PG entrypoint test is the guard. Any new tool must
  return through `_ok`/`_fail`, not bare `json.dumps`.
- **A tool without a breadcrumb fails the suite** — the
  every-tool-has-a-`next_action` test is exhaustive, so registering a tool
  requires a `guidance._NEXT_ACTIONS` entry.
- **Prompts drift from the registry** — S3 gate P1: `/apply` referenced an
  unregistered `record_application`; now registered and pinned by
  `test_prompts_reference_only_registered_tools`.
- **`create_profile` exists though the plan omitted it** (S2.1 improvement) —
  without it `list_profiles`/`set_active_profile` were unusable.
- **`server_info` opens no DB connection**; `source_playbook`/`list_sources`
  are pack-only too (S2 gate P3) — don't add a `_uow()` where packs suffice.
