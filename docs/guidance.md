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

## Shipped default flow (S6.5; `/setup` CV-first since S5.3; URL preview S5.4)

1. `/setup` — CV-first, two intake arms:
   - Pasted CV → `parse_cv` (contact + `setup_hints`) → CONFIRM contact and
     proposed focus (titles/seniority/sectors from `cv_text` + hints; client
     LLM proposes, human confirms) → `update_profile`.
   - LinkedIn/GitHub/portfolio → client opens URL in the user's browser →
     paste visible text → `preview_url_import(url, page_text)` (read-only;
     server never fetches; https-only) → CONFIRM →
     `import_from_url_findings(url, confirmed_fields)` (include `links` /
     `cv_text`).
   Then progressive Tier 2 via `profile_gaps` / `add_achievements` /
   `set_style_profile`. Server never invents.
2. `/hunt` — `hunt_plan` → browser extract (honor `mode: search_box`) →
   `submit_findings` → `list_matches`.
3. `/review` — human decides `approve_match` / `discard_match`.
4. `/apply` — `get_generation_brief` → draft → `submit_asset` →
   `ats_coverage_check` → `start_application` → `report_apply_progress` /
   `resolve_field` → `request_submit` → its decision rules who clicks Submit
   (L0: the human; L1/L2: the agent, once) → `confirm_submitted`. Honor
   portal quirks listed in the fill plan (from the source `apply_playbook`,
   S7.2c).

### `/setup` + `parse_cv` / `preview_url_import` breadcrumbs (S5.3–S5.4)

`SERVER_INSTRUCTIONS` step 1 (`guidance.py:17-19`) names both intake tools:
`parse_cv` or `preview_url_import` → CONFIRM focus →
`update_profile` / `import_from_url_findings`. The `parse_cv` breadcrumb
(`guidance.py:61-68`) tells the client: None = ask; review `setup_hints`
(empty = unknown); propose focus from `cv_text` + hints; CONFIRM; then
`update_profile` with confirmed values + `cv_text`; for a LinkedIn/GitHub URL
use `preview_url_import` instead. The `preview_url_import` breadcrumb
(`guidance.py:54-58`) mirrors CONFIRM-then-`import_from_url_findings`
(including `links` and `cv_text`). The `/setup` prompt (`server.py:673-698`)
has arms 2a (CV) and 2b (URL paste); Tier 2 is one gap at a time, never a
form-wall. Both preview tools are read-only (details: `modules/cv-parsing.md`).

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

The `request_submit` breadcrumb (`guidance.py:92-96`) mirrors the branches;
`get_autopilot_policy` (:97-100) and `autopilot_queue` (:101-105) gained
breadcrumbs when the read-only tools landed (S7.2b). The `/apply` PROMPT
(`server.py:715-740`) deliberately keeps its L0 wording — "At L0 the decision
is await_human" remains literally true; the server-level instructions carry
the full L1/L2 contract.

**Guidance never writes the literal decision verb** (S7.2b): the CI
consent-verb grep fails the build on `submit_authorized` outside
`services/`, so guidance prose says "the submit IS authorized" and leaves the
per-decision directive to the response's `instruction` field — the grep keeps
full strength.

## Destructive erasure (S7.2d)

`delete_my_data` is two-step. The breadcrumb (`guidance.py:108-112`) tells the
client: no token → show the human the summary and `confirm_token`; only call
again with that token if THEY explicitly confirm. The tool docstring
(`server.py:653-660`) forbids inventing a token. This is friction, not
ADR-0005 provenance — see `modules/privacy.md`.

## Tests

`tests/test_mcp_server.py` asserts: every registered tool has a breadcrumb;
instructions state zero-LLM + never-auto-submit; no stale "later sprint"
claims; `/apply` prompt names the full orchestration verbs and mentions
apply_playbook / fill-plan quirks (S7.2c); `/setup` is CV-first, names
`setup_hints` (S5.3), and pins `preview_url_import` → CONFIRM →
`import_from_url_findings` (S5.4).
`tests/test_privacy.py` pins the two-step tool signature (no boolean
`confirm` path).
