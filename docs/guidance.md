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
   `resolve_field` → `request_submit` → its decision rules who clicks Submit
   (L0: the human; L1/L2: the agent, once) → `confirm_submitted`. Honor
   portal quirks listed in the fill plan (from the source `apply_playbook`,
   S7.2c).

## Consent invariant (L0/L1/L2 — S7.2)

`request_submit` is the only place a submit authorization can be constructed.
`SERVER_INSTRUCTIONS` (`guidance.py:26-34`) spells out the decision branches:
`await_human` (L0, the default) means the HUMAN clicks Submit, never the
agent; any other decision means the submit is authorized exactly once — level
1 (the human approved THIS application in the dashboard) or level 2 (their
recorded autopilot policy covers this board/score within the daily cap) — and
the response's `instruction` field says which. The instructions state plainly
that the agent can NEVER create or change a policy (dashboard-only, ADR 0005).
`STEP_KINDS` never includes `"submit"`.

The `request_submit` breadcrumb (`guidance.py:78-82`) mirrors the branches;
`get_autopilot_policy` (:83-86) and `autopilot_queue` (:87-91) gained
breadcrumbs when the read-only tools landed (S7.2b). The `/apply` PROMPT
(`server.py:672-696`) deliberately keeps its L0 wording — "At L0 the decision
is await_human" remains literally true; the server-level instructions carry
the full L1/L2 contract.

**Guidance never writes the literal decision verb** (S7.2b): the CI
consent-verb grep fails the build on `submit_authorized` outside
`services/`, so guidance prose says "the submit IS authorized" and leaves the
per-decision directive to the response's `instruction` field — the grep keeps
full strength.

## Destructive erasure (S7.2d)

`delete_my_data` is two-step. The breadcrumb (`guidance.py:94-98`) tells the
client: no token → show the human the summary and `confirm_token`; only call
again with that token if THEY explicitly confirm. The tool docstring
(`server.py:627-633`) forbids inventing a token. This is friction, not
ADR-0005 provenance — see `modules/privacy.md`.

## Tests

`tests/test_mcp_server.py` asserts: every registered tool has a breadcrumb;
instructions state zero-LLM + never-auto-submit; no stale "later sprint"
claims; `/apply` prompt names the full orchestration verbs and mentions
apply_playbook / fill-plan quirks (S7.2c).
`tests/test_privacy.py` pins the two-step tool signature (no boolean
`confirm` path).
