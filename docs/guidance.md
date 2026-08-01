# MCP guidance + prompts (client behavioral contract)

The MCP server never browses and never calls an LLM. The client agent reads
`SERVER_INSTRUCTIONS` (server-level) and the `/setup`, `/hunt`, `/review`,
`/apply` prompts, then acts in the user's browser.

## Source of truth

- [`src/mcpforwork/entrypoints/mcp/guidance.py`](../src/mcpforwork/entrypoints/mcp/guidance.py)
  — `SERVER_INSTRUCTIONS` + `next_action(tool)` breadcrumbs. Dependency-free
  (import-linter contract).
- [`src/mcpforwork/entrypoints/mcp/server.py`](../src/mcpforwork/entrypoints/mcp/server.py)
  — `@mcp.prompt` definitions.

## Shipped default flow (S6.5)

1. `/setup` — profile (Tier 1 + progressive Tier 2), `parse_cv`, achievements,
   style.
2. `/hunt` — `hunt_plan` → browser extract (honor `mode: search_box`) →
   `submit_findings` → `list_matches`.
3. `/review` — human decides `approve_match` / `discard_match`.
4. `/apply` — `get_generation_brief` → draft → `submit_asset` →
   `ats_coverage_check` → `start_application` → `report_apply_progress` /
   `resolve_field` → `request_submit` → **human clicks Submit at L0** →
   `confirm_submitted`.

## Consent invariant (L0 today)

`request_submit` is the only place a submit authorization can be constructed.
At L0 it always returns `await_human`. Autopilot L1/L2 (dashboard approval /
recorded policy) lands in Sprint 7; guidance will gain those branches then.
`STEP_KINDS` never includes `"submit"`.

## Tests

`tests/test_mcp_server.py` asserts: every registered tool has a breadcrumb;
instructions state zero-LLM + never-auto-submit; no stale "later sprint"
claims; `/apply` prompt names the full orchestration verbs.
