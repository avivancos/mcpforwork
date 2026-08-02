# CLI & packaging (mcpforwork init / serve / version / connect)

> The self-host front door: a stdlib-argparse CLI shipped as the `mcpforwork`
> console script, plus the uvx-installable packaging that makes
> `uvx --from mcpforwork mcpforwork init` the README quickstart. Cards:
> S6.7 (connect), S5.3 (init / serve / version + packaging).

## How it works

`src/mcpforwork/entrypoints/cli/main.py` — `main(argv)` (`main.py:72`)
dispatches four subcommands; no args prints usage to stderr and exits 2.

- `init` -> `_init` (`main.py:27`): creates `config.data_dir()`, opens
  `connect(config.db_url())` (runs migrations to `SCHEMA_VERSION`), prints
  the redacted DB URL, the claude-code local block, a pointer to
  `mcpforwork connect`, and a "run /setup next" hint. Idempotent.
- `serve` -> `_serve` (`main.py:43`): imports and runs
  `mcpforwork.entrypoints.mcp.server:main` — the ONE sanctioned cli->mcp edge
  (serve is a launcher, not a reimplementation). The `run` parameter is
  injectable so dispatch is testable without the blocking stdio loop.
- `version` -> `_version` (`main.py:52`): `importlib.metadata.version`, falls
  back to `"unknown"` when the package metadata is absent.
- `connect` -> `_connect` (`main.py:60`): prints the client config block(s).
  argparse validates `--client`/`--mode` choices itself; a `ValueError` from
  the formatter maps to stderr + exit 2.

### connect formatters (S6.7)

`src/mcpforwork/entrypoints/cli/connect.py` — pure str->str formatters,
stdlib only (`json`), print-only: the command never writes the user's config
files. `render(client, mode)` (`connect.py:87`) assembles header + body +
mode-specific annotations; `render_all(mode)` (`connect.py:103`) joins all
five clients with blank lines. The 5 clients x 2 modes matrix (`_BODIES`,
`connect.py:73`):

- **local** (default) — stdio `uvx --from mcpforwork mcpforwork-mcp`:
  - claude-code / claude-desktop / cursor -> JSON `{"mcpServers": …}`
    (`_local_json`). claude-desktop additionally prints its macOS
    (`~/Library/Application Support/Claude/claude_desktop_config.json`) and
    Windows (`%APPDATA%\Claude\claude_desktop_config.json`) config-file paths
    (`_DESKTOP_PATHS`, `connect.py:32`).
  - codex -> TOML `[mcp_servers.mcpforwork]` with `command`/`args`
    (`_codex_local`).
  - opencode -> JSON `{"mcp": …, "type": "local", "command": ["uvx", …]}`
    (`_opencode_local`).
- **compose** — streamable-HTTP at `http://localhost:8500/mcp`:
  - JSON clients get `{"type": "http", "url": …}` (`_compose_json`); codex
    gets `url = "…"` (`_codex_compose`); opencode gets `"type": "remote"`.
  - Every compose block ends with the two-line single-tenant caveat
    (`_CAVEAT`, `connect.py:19`): the networked MCP shares the one local
    user; multi-tenant HTTP auth is hosted scope (ADR 0006).

**Packaging** (`pyproject.toml`): three console scripts at
`[project.scripts]` (`pyproject.toml:37-40`) — `mcpforwork` (this CLI),
`mcpforwork-mcp` (stdio server), `mcpforwork-api` (parity API). Hatchling
backend (`:42-44`); version read from `src/mcpforwork/__init__.py`
(`:46-47`); wheel ships `src/mcpforwork` (`:49-50`). The README quickstart
(`README.md:8-19`) is the user-facing contract.

**Entrypoint-independence contracts** (`pyproject.toml:99-121`, enforced by
`uv run lint-imports`): the MCP server never imports cli/api; the API never
imports mcp/cli; the CLI never imports the API. `cli -> mcp.server.main` is
the documented launcher exception.

## Design decisions

- **stdlib argparse, no Typer/click** (S5.3 spec, charter §3): one CLI does
  not justify a dependency; S6.7 extended the same parser.
- **Print-only connect**: their editor, their paste — the CLI never writes
  client config files, so there is nothing to corrupt and no permission
  surface to secure.
- **Pure formatters behind a dispatch table**: one function per client+mode,
  str in -> str out, so every golden block is trivially testable and `_BODIES`
  replaces branching.
- **`_init` reuses `connect_cmd.render("claude-code", "local")`**
  (`main.py:35`) instead of keeping its own snippet constant — the old
  `_SNIPPET` duplication was removed after the S6.7 review gate; the uvx
  block now has exactly one source of truth and init cannot drift from
  connect.
- **serve delegates, not duplicates**: a single in-process call into the MCP
  server main keeps the serving surface defined in exactly one place.
- **`_redact` (`main.py:15`)**: any password in the configured DB URL is
  masked before printing (shell history, CI logs); SQLite URLs carry no
  secret and pass through unchanged.

## Testing

`tests/test_cli.py` (8 tests) + `tests/test_cli_connect.py` (17 tests) —
zero mocks, real SQLite at `tmp_path`:

- init creates a migrated db (`PRAGMA user_version == SCHEMA_VERSION`) and is
  idempotent; `test_init_points_at_connect` pins the connect pointer.
- version prints; no-args -> exit 2 with usage on stderr; `--help` exits 0
  (SystemExit) and lists the subcommands.
- `test_serve_invokes_the_runner`: dispatch via injected `run`;
  `test_serve_dispatch_target_is_importable` pins the real `mcp.server.main`.
- `_redact` masks a Postgres password while keeping user/host visible.
- connect: golden full-block outputs per client x mode (exact text, not
  substrings — config drift must fail loudly); every emitted JSON block
  parses (`json.loads`) and both codex TOML blocks parse (`tomllib`) with
  structural asserts on command/args/url; the caveat is present in every
  compose block and absent (with `localhost:8500`) from every local block;
  unknown client/mode -> `ValueError`; CLI dispatch covers the all-clients
  default, a single client, and argparse rejecting `--client vscode` with
  SystemExit(2).

## Gotchas

- **S6.7 review-gate story**: first gate FAIL — P1: the codex/opencode
  compose tests lacked structural asserts, so mutants survived; P2: the
  caveat was substring-checked only, and `_SNIPPET` duplicated the uvx block.
  Fixed with parse-based structural asserts and the render reuse above;
  second gate PASS with the mutants observed killed.
- **import-linter checks module edges, not symbols**: a rename of
  `mcp.server.main` would pass lint-imports yet break `mcpforwork serve` at
  runtime — keep `test_serve_dispatch_target_is_importable` when refactoring
  the server entrypoint.
- **Password redaction was a gate P2** (commit `66e717b`): any new stdout
  path that echoes configuration must go through `_redact`.
- `argparse --help` raises `SystemExit(0)` and invalid `--choices` values
  raise `SystemExit(2)` — assert via `pytest.raises`, not a return code.
- The S5.3 demo gate (clean tmp HOME -> init -> serve smoke -> onboard ->
  hunt plan, zero LLM calls) is the card's manual proof, not an automated
  test; rerun it if init/serve wiring changes shape.
