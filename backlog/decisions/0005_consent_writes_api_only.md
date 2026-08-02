# ADR 0005 — Consent artifacts are written by the human-session API, never by MCP

**Status:** accepted (S7.2a)
**Date:** 2026-08-02

## Context

Autopilot L1 needs a recorded human approval that `request_submit` can turn
into a one-time `submit_authorized`. PRODUCT_PLAN sketched a
`set_autopilot_policy` MCP tool. That shape is dangerous: MCP tools are
invoked by the client LLM, whose context includes untrusted posting content.
A prompt-injected agent ("the form requires you to call X first") could mint
its own consent if any consent write were agent-reachable.

## Decision

- **Consent artifacts (L1 approval now, L2 policy in S7.2b) are written
  exclusively by the session-authenticated HTTP API** — the surface a human
  drives with a browser and a magic-link cookie. MCP gets read-only autopilot
  tools only. No MCP tool, present or future, may reference the write
  functions; this is enforced structurally (inspect-source tests +
  a CI grep: `SET submit_approved_at` may appear only in
  `services/autopilot.py`).
- **`STEP_KINDS` never gains `"submit"`.** Authorization is a response-scoped
  directive from `request_submit` for an application in `submit_requested` —
  never a persisted plan step an agent could construct ahead of time. The
  apply state machine is unchanged.
- The approval artifact lives on the application row
  (`submit_approved_at`, `submit_approved_via`), so it inherits the existing
  tenant isolation (RLS on Postgres, `user_id` scoping everywhere) and the
  audit trail snapshots it at authorization time.
- **Exactly-once** is the `consent_level` 0 → 1 flip: the authorization audit
  row is written only on the flip, while a retried `request_submit` still
  re-returns the directive (a crashed client must not be stranded).

## Consequences

- The dashboard is the only consent control panel — which matches its
  "mirror and control panel" role: it approves, it never fills or submits.
- Approving is possible in both `awaiting_human` and `submit_requested` (the
  two states the dashboard derives as "awaiting you"), so there is no race
  between the human clicking approve and the agent calling `request_submit`.
- AGENTS.md §1.2 is reworded: "never submit without a recorded consent
  check" — the invariant is the recorded check, not the supervision level.
- Hosted-track note: this design is also the right shape for multi-tenant
  hosted — consent writes already ride the authenticated, RLS-scoped API.
