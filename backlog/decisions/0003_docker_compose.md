# ADR 0003 — Docker images + `docker compose` topology

**Status:** Accepted · 2026-07-11
**Card:** `backlog/in_progress/W1.2_docker_compose.md`

## Context

`PRODUCT_PLAN.md` names Docker in two places — self-host (`docker compose up`,
S5.3) and the hosted alpha (S6). The user asked to containerize the whole
product now ("a general mcpforwork docker") bringing up the Next.js web
surfaces (W1.1) alongside the Python MCP server. Containerization is a new
infra surface not in the §Architecture spec, so it takes an ADR.

Two facts shape the topology:
- The only Python entrypoint today is `mcpforwork-mcp` (`pyproject.toml`
  `[project.scripts]`), a **FastMCP** server. It defaults to **stdio** but
  honors `MCPFORWORK_TRANSPORT` — `streamable-http` makes it a real networked
  MCP endpoint (the transport the hosted connector will use).
- `entrypoints/api/` (the FastAPI parity layer the dashboard reads from, per
  ADR 0002) **does not exist yet** — flagged S6.x gap. So the web container
  cannot talk to a real backend today; it runs on the fixtures adapter.

## Decision

### Two services, one compose, one data volume

`docker-compose.yml` at the repo root defines:

- **`mcp`** — the Python self-host image (root `Dockerfile`, `uv`-based).
  Runs `mcpforwork-mcp` with `MCPFORWORK_TRANSPORT=streamable-http`,
  `FASTMCP_HOST=0.0.0.0`, `FASTMCP_PORT=8000` → a networked MCP connector at
  `http://localhost:8000/mcp`. SQLite lives on a named volume via
  `MCPFORWORK_DATA_DIR=/data`. This is the genuine self-host artifact (S5.3),
  and doubles as the local connector endpoint an AI client can point at.
- **`web`** — the Next.js image (`web/Dockerfile`, standalone output). Serves
  landing + docs + dashboard on `:3000`. Runs with `MCPFORWORK_FIXTURES=1`
  because there is no parity API yet; the fail-closed guard (ADR 0002) would
  otherwise refuse to boot in production without `MCPFORWORK_API_URL`.

### The web ↔ API wiring is staged, not faked

The compose leaves `MCPFORWORK_API_URL` **commented** on the `web` service with
a one-line note. When S6.x ships `entrypoints/api/`, that becomes an `api`
service (or a route on `mcp`) and uncommenting the env flips the dashboard off
fixtures onto the real backend — the ADR-0002 config swap, now a compose edit.
We do **not** invent an API container or a fake backend to make the wiring look
complete (honesty invariant; would violate the no-mocks discipline in spirit).

### Images

- **Python (`Dockerfile`, context repo root):** multi-stage — `uv sync
  --locked --no-dev` into a venv on the official `uv` image, copied into a slim
  `python:3.12-slim` runtime. Non-root user, `/data` volume, `EXPOSE 8000`.
  Root `.dockerignore` excludes `web/`, `.venv/`, tests, and VCS so the Python
  context stays small.
- **Web (`web/Dockerfile`, context `web/`):** multi-stage — `npm ci
  --ignore-scripts` → `npm run build` (standalone) → a `node:24-alpine` runner
  carrying only `.next/standalone` + `.next/static`. Non-root, `EXPOSE 3000`.

## Alternatives rejected

- **One image running both** — couples two toolchains (uv + node) and two
  lifecycles in one container; compose is the right seam.
- **A stub/fake `api` service** — dishonest; the gap is real and flagged.
- **Running `mcp` as stdio in compose** — a stdio process with no attached
  client is a no-op daemon. `streamable-http` is both truthful and useful.
- **Bind-mounting source for "dev" containers** — YAGNI; the local `npm run
  dev` / `uv run` flows already exist. These images are for parity/self-host.

## Consequences

- `docker compose up` yields a working dashboard demo (:3000, fixtures) and a
  live MCP connector endpoint (:8000/mcp) sharing a SQLite volume.
- The images are additive: no Python source, CI job, or the Python test suite
  changes. `web/` and root build contexts are isolated by their `.dockerignore`s.
- S6.x owns: the `api` service, uncommenting `MCPFORWORK_API_URL`, and a real
  healthcheck on the MCP HTTP endpoint. Recorded on the W1.2 card.
