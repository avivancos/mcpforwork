# Internal engineering docs

Granular, module-scoped documentation of how each feature was developed:
mechanics, invariants, design decisions, testing approach, and gotchas.
Written by the **documentor** subagent (`.claude/agents/documentor.md`) after
every card closes; the index below is reconciled by the closing agent.

User-facing docs live in the repo README and the web docs pages
(`web/src/app/docs/`). Product spec: [PRODUCT_PLAN.md](PRODUCT_PLAN.md).

## Index

### Platform core
- [modules/repo-harness.md](modules/repo-harness.md) — bootstrap, test harness, hexagonal skeleton (S0.x)
- [modules/database.md](modules/database.md) — SQLite/Postgres adapters, migrations, RLS (S1.1–S1.2)
- [modules/profiles.md](modules/profiles.md) — profile schema + service (S1.3)
- [modules/dedup.md](modules/dedup.md) — dedup engine (S1.4)

### MCP surface
- [modules/mcp-server.md](modules/mcp-server.md) — entrypoint, tools, wiring, read-only consent tools, delete_my_data two-step (S2.1, S7.2, S7.2d)
- [modules/packs.md](modules/packs.md) — packs-as-data: schema, geo packs, `search_box`, `apply_playbook` contract (https-only `form_url_pattern`, quirks → fill plan), honest-empty `auto_apply_safe` after S7.2c browser pass (S2.3–S2.6, S7.2c)
- [modules/hunt.md](modules/hunt.md) — hunt pipeline; `apply_hint` / `apply_playbook` from packs (S2.4, S2.6, S7.2c)
- [modules/generation.md](modules/generation.md) — briefs, assets, ATS coverage, review tools (S3.x)
- [guidance.md](guidance.md) — client behavioral contract: instructions, prompts, breadcrumbs; CV-first `/setup` + URL preview (`preview_url_import`); `/apply` honors fill-plan quirks (S5.3–S5.4, S6.5, S7.2, S7.2c, S7.2d)

### Apply loop
- [modules/apply.md](modules/apply.md) — state machine, progress loop, consent gate, L1 approval loop, L2 policy branch + cap TOCTOU serialization, fill-plan quirks from `apply_playbook`, obstacles, abandon (S4.x, S6.0, S7.2a–S7.2d)
- [modules/autopilot.md](modules/autopilot.md) — consent artifacts write side (ADR 0005): L1 approval, L2 policy CRUD + evaluate + queue, `safe_source_slugs` from packs (empty post-S7.2c), CI consent-write gate (S7.2a–S7.2c; TOCTOU closed S7.2d)

### CV + CLI
- [modules/cv-parsing.md](modules/cv-parsing.md) — CV parser, evidence-only `setup_hints`, `preview_url_import` (https-only, never fetches), progressive Tier 2 (S5.4, S5.3, S5.1–S5.2)
- [modules/cli.md](modules/cli.md) — CLI packaging (`S5.3_cli_packaging`, S6.7)

### API (Starlette parity API)
- [api/auth.md](api/auth.md) — magic-link auth, session store (S6.1a–S6.1b)
- [api/hardening.md](api/hardening.md) — self-host hardening: body cap, TrustedHost, cookie-secure (S6.1c)
- [api/pipeline.md](api/pipeline.md) — pipeline reads, stats, match detail, consent seam (S6.6a, S6.9, W6.2)
- [api/actions.md](api/actions.md) — match actions, profile mapping, error kinds (S6.6b, S6.10)
- [api/account.md](api/account.md) — account endpoints, sessions, audit, connection (S6.6c)
- [api/autopilot.md](api/autopilot.md) — L2 policy routes (consent writes, ADR 0005), camelCase seam, boards list (honestly empty post-S7.2c) (S7.2b, W6.3)

### Privacy
- [modules/privacy.md](modules/privacy.md) — GDPR export/delete; MCP two-step confirm tokens (S6.4, S6.6c, S7.2b, S7.2d)

### Web dashboard
- [modules/web.md](modules/web.md) — Next.js surfaces, fixtures, CI step, merge, L1 approval UI, L2 autopilot policy UI (W1–W6.3, S6.3)

### Self-host topology
- [modules/self-host.md](modules/self-host.md) — compose stack, tenant alignment, connect (S6.8, ADR 0006)
