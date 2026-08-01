# Repo harness — bootstrap, boundaries, CI, test conventions

> The substrate every card stands on: uv/hatchling packaging, ruff, pytest
> config, the hexagonal layer skeleton with import-linter contracts, the CI
> gate pipeline, and the zero-mocks test harness conventions. Built by Sprint
> 0 (latest first: S0.4 test harness, S0.3 hexagonal skeleton + CI, S0.2
> harness install, S0.1 repo bootstrap).

## How it works

**Packaging.** `pyproject.toml` — uv-managed, hatchling build, `src/` layout,
Python >=3.12. The version is dynamic from `src/mcpforwork/__init__.py:8`
(`__version__`), single-sourced (hatch reads it at build time). Runtime deps
are minimal (`mcp`, `pyyaml`, `itsdangerous`, `starlette`, `uvicorn`);
`psycopg[binary]` is an optional `postgres` extra (pyproject.toml:22-25) so
SQLite self-host installs stay driver-free. Dev group: pytest,
pytest-httpserver, ruff, import-linter, psycopg, httpx (pyproject.toml:27-35).
Console scripts: `mcpforwork`, `mcpforwork-mcp`, `mcpforwork-api`
(pyproject.toml:37-40).

**Layers.** `src/mcpforwork/{domain,services,ports,adapters,entrypoints,packs}`
— each `__init__.py` docstring states the layer's boundary rule. domain is
pure (no I/O, imports no other layer); services are use cases with
`(uow, user_id, ...)` signatures, caller commits; ports are
`typing.Protocol` seams only; adapters implement the ports; entrypoints are
thin (auth + serialization only); packs are DATA, not code.

**Boundary contracts.** Eight import-linter contracts in
`pyproject.toml:67-152`, run by `uv run lint-imports` locally and in CI:
domain imports no other layer; services never import adapters/entrypoints;
ports are pure seams; entrypoints never import each other (MCP↛CLI/API,
API↛MCP/CLI, CLI↛API); the MCP guidance module is dependency-free; and no LLM
SDK (`openai`, `anthropic`, `litellm`, `cohere`, `mistralai`, `groq`,
`google`, `langchain`, `llama_index`) is importable anywhere in the package —
the zero server-side LLM invariant enforced as a build failure.

**CI.** `.github/workflows/ci.yml`: `uv sync --locked` → ruff format --check →
ruff check → lint-imports → consent-verb grep gate → no-substring-error
gate → pytest. `permissions: contents: read`; actions are SHA-pinned
(checkout v4.2.1, setup-uv v5.4). A separate `web` job covers the Next.js
toolchain in isolation (ADR 0002).

**Test harness.** `tests/conftest.py`:
- `conn` (conftest.py:21-35) — a REAL SQLite file at `tmp_path` (never
  `:memory:`), `sqlite3.Row` factory, `PRAGMA foreign_keys=ON`,
  `busy_timeout=30000`. Virgin (un-migrated) — migration tests need that.
- `uow` (conftest.py:38-47) — a migrated `UnitOfWork` on a real file; the
  seam services take.
- `any_uow` (conftest.py:59-93) — the parity matrix: SQLite always, Postgres
  under `-m live` with `TEST_POSTGRES_URL` (see docs/modules/database.md).
- `mcp_env` (conftest.py:50-56) — points the MCP tools at a tmp DB via env
  vars (added with the hunt pipeline, S2.4).

pytest config: `testpaths = ["tests"]`, `addopts = "-m 'not live'"`, the
`live` marker registered (pyproject.toml:60-65).

**Agent harness.** `AGENTS.md` is the source of truth (invariants,
architecture, charter, testing contract, backlog workflow, review gate,
commits); `CLAUDE.md` is a thin complement. `backlog/` holds the card kit
(`agent_index.md`, `_TEMPLATE.md`, the seven state dirs — the folder a card
sits in IS its state) and ADRs in `backlog/decisions/` (0001 records the
bootstrap decisions).

## Design decisions

- **Harness before features** (S0.2): reviewers, backlog kit, and AGENTS.md
  were installed in Sprint 0 so every later card runs inside the quality
  system. The gate itself was exercised on Sprint 0's diff and caught a real
  P1 — the sprint's demo-gate criterion.
- **Architecture drift fails the build, not review** (S0.3): boundary rules
  are import-linter contracts in CI, deliberately probed with violations
  (domain→adapters import, `import openai` in services — both exit 1, then
  reverted).
- **The review gate evolved**: S0.2 installed four reviewer subagents; ADR
  0007 later fused them into the single `test-code-reviewer` (test audit +
  code review + regression audit). `.claude/agents/` today holds only that
  fused reviewer plus the documentor.
- **Version single-sourced** via hatch dynamic versioning (S0.1 gate P3:
  pyproject had duplicated it).
- **Deferred until the rule of two triggered**: the entrypoint-independence
  contracts were specced in S0.3 but only added once further entrypoints
  existed (carried in ADR 0001).

## Testing

- `tests/test_harness.py` — the harness tests itself: the package exposes a
  version; the `conn` fixture is backed by a real file (asserted via
  `PRAGMA database_list`, so a `:memory:` mutant fails the suite) and
  enforces foreign keys (an FK-violating insert raises); `busy_timeout` is
  asserted too.
- `uv run pytest` excludes `live` by default; `uv run pytest -m live` is the
  pre-push arm (needs Docker Postgres).
- Local gate trio (AGENTS.md §8): `uv run ruff format --check .`,
  `uv run ruff check .`, `uv run lint-imports`.

## Gotchas

- **Consent-verb gate hardened twice** (S0.3): line-content filtering failed
  open via a comment trick; `--exclude-dir` matched nested `*/services/`
  dirs. The final form anchors on grep's path prefix:
  `grep -RIn … | grep -v '^src/mcpforwork/services/'` (ci.yml:31-41), probed
  against both bypasses.
- **`check_same_thread=False` was dropped** from the `conn` fixture (S0.4
  gate P3) — unspecced, no threaded consumer; reintroduce only with the card
  that needs it.
- **Card `State:` header removed** (S0.2) — it drifted on its very first
  move; the folder is the only state source.
- **The zero-LLM contract was widened** from 4 layers × 2 SDKs to the whole
  package × 9 SDK roots (gate P2). Externals are squashed to their root, so
  `google` covers `google.genai` (pyproject.toml:147-148).
- **A second CI grep gate** (ci.yml:43-50) bans substring error matching in
  the API entrypoint — added by S6.10, not Sprint 0.
