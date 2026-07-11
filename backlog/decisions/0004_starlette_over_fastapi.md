# ADR 0004 — Parity API framework: Starlette, not FastAPI

**Status:** Accepted · 2026-07-12
**Card:** `backlog/in_progress/S6.1b_auth_http_layer.md`
**Amends:** ADR 0002 (which named "FastAPI parity endpoints")

## Context

`PRODUCT_PLAN.md §Architecture` and ADR 0002 name **FastAPI** for the
`entrypoints/api/` parity layer the web dashboard reads. Building the first slice
(S6.1b) forced the question before code: FastAPI is **not installed**, and adding
it pulls `fastapi` + `pydantic` + `pydantic-core` (a compiled dependency) into a
project whose charter budgets every dependency with a justification line.

Meanwhile **Starlette, uvicorn, and httpx are already transitive via `mcp`**
(FastMCP's streamable-http transport). Starlette is the ASGI framework FastAPI
itself is built on.

The parity API is thin: ~5–20 routes that authenticate via the magic-link
session cookie and delegate to existing services (which already validate and own
all domain logic). It does not need FastAPI's request-model validation or
OpenAPI generation — validation lives in the services, and the contract is
pinned by the web loop's typed seam (`web/src/lib/api/`), not an OpenAPI doc.

## Decision

Build `entrypoints/api/` on **Starlette** (+ uvicorn to serve). Declare
`starlette` and `uvicorn` as **direct** runtime dependencies (they were already
transitive; declaring them is honest and pin-stable if `mcp` relaxes its
floors), and `httpx` as a dev dependency (Starlette's `TestClient` transport →
real, zero-mock HTTP tests).

- No new *compiled* dependency (no pydantic-core); no net new package in the
  resolved tree today.
- Handlers hand-shape JSON responses (a tiny `_JSON` with a datetime default);
  input is a small amount of explicit parsing, not a validation framework.

## Alternatives rejected

- **FastAPI** (the ADR-0002 name) — adds fastapi + pydantic(+core) for
  ergonomics this thin, service-delegating layer doesn't need; the services are
  the validation boundary. Reconsider only if the API grows request schemas
  complex enough that hand-parsing becomes error-prone.
- **Flask / Django REST** — sync stacks, not ASGI; would not share uvicorn with
  the MCP streamable-http transport.

## Consequences

- ADR 0002's "FastAPI" wording is superseded by this ADR for the API layer;
  the web-facing contract (paths + shapes) is unchanged.
- If a future card genuinely needs pydantic-grade validation or auto-generated
  OpenAPI for external API consumers, revisit with a follow-up ADR — the route
  handlers are plain functions and would migrate to FastAPI incrementally.
