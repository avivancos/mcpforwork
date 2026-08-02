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
- [modules/packs.md](modules/packs.md) — packs-as-data: schema, seed, geo packs, board verification, `auto_apply_safe` gating (S2.3–S2.6, S7.2b)
- [modules/hunt.md](modules/hunt.md) — hunt pipeline (S2.4)
- [modules/generation.md](modules/generation.md) — briefs, assets, ATS coverage, review tools (S3.x)
- [guidance.md](guidance.md) — client behavioral contract: instructions, prompts, breadcrumbs (S6.5, S7.2, S7.2d)

### Apply loop
- [modules/apply.md](modules/apply.md) — state machine, progress loop, consent gate, L1 approval loop, L2 policy branch + cap TOCTOU serialization, obstacles, abandon (S4.x, S6.0, S7.2a–S7.2d)
- [modules/autopilot.md](modules/autopilot.md) — consent artifacts write side (ADR 0005): L1 approval, L2 policy CRUD + evaluate + queue, CI consent-write gate (S7.2a–S7.2b; TOCTOU closed S7.2d)

### CV + CLI
- [modules/cv-parsing.md](modules/cv-parsing.md) — CV parser, progressive Tier 2 (S5.1–S5.2)
- [modules/cli.md](modules/cli.md) — CLI packaging (S5.3)

### API (Starlette parity API)
- [api/auth.md](api/auth.md) — magic-link auth, session store (S6.1a–S6.1b)
- [api/hardening.md](api/hardening.md) — self-host hardening: body cap, TrustedHost, cookie-secure (S6.1c)
- [api/pipeline.md](api/pipeline.md) — pipeline reads, stats, match detail, consent seam (S6.6a, S6.9, W6.2)
- [api/actions.md](api/actions.md) — match actions, profile mapping, error kinds (S6.6b, S6.10)
- [api/account.md](api/account.md) — account endpoints, sessions, audit, connection (S6.6c)
- [api/autopilot.md](api/autopilot.md) — L2 policy routes (consent writes, ADR 0005), camelCase seam, boards list (S7.2b, W6.3)

### Privacy
- [modules/privacy.md](modules/privacy.md) — GDPR export/delete; MCP two-step confirm tokens (S6.4, S6.6c, S7.2b, S7.2d)

### Web dashboard
- [modules/web.md](modules/web.md) — Next.js surfaces, fixtures, CI step, merge, L1 approval UI, L2 autopilot policy UI (W1–W6.3, S6.3)

### Self-host topology
- [modules/self-host.md](modules/self-host.md) — compose stack, tenant alignment, connect (S6.8, ADR 0006)
