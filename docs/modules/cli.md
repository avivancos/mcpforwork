# CLI & packaging (mcpforwork init / serve / version)

> The self-host front door: a stdlib-argparse CLI shipped as the `mcpforwork`
> console script, plus the uvx-installable packaging that makes
> `uvx --from mcpforwork mcpforwork init` the README quickstart. Card: S5.3.

## How it works

`src/mcpforwork/entrypoints/cli/main.py` — `main(argv)` (`main.py:63`)
dispatches three subcommands; no args prints usage to stderr and exits 2.

- `init` -> `_init` (`main.py:34`): creates `config.data_dir()`, opens
  `connect(config.db_url())` (which runs migrations to `SCHEMA_VERSION`),
  prints the redacted DB URL, the `.mcp.json` connector snippet (`_SNIPPET`,
  `main.py:27` — launches the `mcpforwork-mcp` script via uvx), and a "run
  /setup next" hint. Idempotent.
- `serve` -> `_serve` (`main.py:46`): imports and runs
  `mcpforwork.entrypoints.mcp.server:main` — the ONE sanctioned cli->mcp edge
  (serve is a launcher, not a reimplementation). The `run` parameter is
  injectable so dispatch is testable without the blocking stdio loop.
- `version` -> `_version` (`main.py:55`): `importlib.metadata.version`, falls
  back to `"unknown"` when the package metadata is absent.

**Packaging** (`pyproject.toml`): three console scripts at
`[project.scripts]` (`pyproject.toml:37-40`) — `mcpforwork` (this CLI),
`mcpforwork-mcp` (stdio server), `mcpforwork-api` (parity API). Hatchling
backend (`:42-44`); version read from `src/mcpforwork/__init__.py:8`
(`[tool.hatch.version]`, `:46-47`); wheel ships `src/mcpforwork` (`:49-50`).
The README quickstart (`README.md:8-19`) is the user-facing contract:
`uvx --from mcpforwork mcpforwork init` + the `.mcp.json` snippet.

**Entrypoint-independence contracts** (`pyproject.toml:99-121`, enforced by
`uv run lint-imports`): the MCP server never imports cli/api; the API never
imports mcp/cli; the CLI never imports the API. `cli -> mcp.server.main` is
the documented launcher exception — the card considered and rejected hiding it
behind an abstraction.

## Design decisions

- **stdlib argparse, no Typer/click** (card spec, anti-over-engineering
  charter §3): one CLI does not justify a dependency.
- **serve delegates, not duplicates**: a single in-process call into the MCP
  server main keeps the serving surface defined in exactly one place.
- **`_redact` (`main.py:15`)**: any password in the configured DB URL is
  masked before printing (shell history, CI logs); SQLite URLs carry no
  secret and pass through unchanged.
- **init prints the snippet** because the next user step is always "wire the
  MCP client" — the command ends where the README continues.

## Testing

`tests/test_cli.py` (8 tests, zero mocks — real SQLite at `tmp_path`):

- init creates a migrated db (`PRAGMA user_version == SCHEMA_VERSION`) and
  prints the snippet; init is idempotent.
- version prints; no-args -> exit 2 with usage on stderr; `--help` exits 0
  (SystemExit) and lists all three subcommands.
- `test_serve_invokes_the_runner`: dispatch via injected `run`.
- `test_serve_dispatch_target_is_importable`: pins the real
  `mcp.server.main` symbol.
- `_redact` masks a Postgres password while keeping user/host visible.

## Gotchas

- **import-linter checks module edges, not symbols**: a rename of
  `mcp.server.main` would pass lint-imports yet break `mcpforwork serve` at
  runtime — that is exactly why `test_serve_dispatch_target_is_importable`
  exists. Keep it when refactoring the server entrypoint.
- **Password redaction was a gate P2** (commit `66e717b`): init originally
  printed the raw DB URL. Any new stdout path that echoes configuration must
  go through `_redact`.
- `argparse --help` raises `SystemExit(0)` — assert via `pytest.raises`, not
  a return code.
- The S5.3 demo gate (clean tmp HOME -> init -> serve smoke -> onboard ->
  hunt plan, zero LLM calls) is the card's manual proof, not an automated
  test; rerun it if init/serve wiring changes shape.
