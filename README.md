# mcpfor.work

Open-source, MCP-first job-search copilot — any sector, any country. Self-hostable for free; hosted at a flat $5/mo.

**Status: pre-alpha.** Self-host works end-to-end (profile → hunt → briefs →
supervised apply); hosted is not launched yet.

## Quickstart (self-host, zero account)

```bash
uvx --from mcpforwork mcpforwork init     # creates ~/.mcpforwork/mcpforwork.db
```

Add the connector to Claude Code / Desktop (`.mcp.json`):

```json
{ "mcpServers": { "mcpforwork": { "command": "uvx",
    "args": ["--from", "mcpforwork", "mcpforwork-mcp"] } } }
```

Then, in your client: `/setup` (build your profile, < 3 min) → `/hunt`
(browser-verified job-portal searches; UK, Spain, US, DE + remote boards) →
`/review` → `/apply` (honest drafts + coverage check; **you** click Submit —
the copilot never auto-submits). Zero server-side LLM calls, ever.

## What makes it different

- **The LLM is the client.** All intelligence runs inside your own Claude or ChatGPT/Codex subscription connected to this MCP server. We never make server-side LLM calls, so the hosted plan is infrastructure, not token resale.
- **Graduated autonomy, consent-based.** Default is supervised: the copilot prepares, you review and submit. Autopilot is explicit opt-in, policy-governed, and only ever runs in your own browser session.
- **Open-core.** The full product self-hosts on SQLite with no account. Hosted adds convenience: remote MCP connector, web dashboard, sync, backups.
- **Never fabricate.** Generation briefs carry a facts inventory — drafts may only claim what your profile proves.
- **Sector- and country-agnostic by data.** Job-site knowledge ships as versioned, community-contributable packs, not code releases.
- **You own your data.** Export and delete built in.

## Architecture

Pragmatic hexagonal (ports & adapters) over a modular monolith. The full product
specification lives in [docs/PRODUCT_PLAN.md](docs/PRODUCT_PLAN.md); contributor
rules in [AGENTS.md](AGENTS.md).

## Development

```bash
uv sync
uv run pytest
uv run ruff format --check . && uv run ruff check .
uv run lint-imports
```

## License

Apache-2.0
