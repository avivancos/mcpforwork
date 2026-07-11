# S4 demo — one full REAL application via the browser (human clicks Submit)

**Epic:** Sprint 4 — Browser-apply orchestration
**State:** need_human_testing

## Pending human testing

1. **What was built + why the agent can't close verification:** the complete
   supervised apply loop (start_application → step plan → report_apply_progress
   → resolve_field → request_submit → confirm_submitted). The final proof is a
   REAL job application submitted to a REAL employer — an irreversible,
   outward-facing action only the human may take (consent invariant §1.2).
   An agent must never submit a job application on its own.

2. **Exact steps for the human (with Claude in the loop):**
   a. `MCPFORWORK_DB_URL=sqlite:///~/.mcpforwork/mcpforwork.db uv run mcpforwork-mcp`
      wired into Claude Code/Desktop via `.mcp.json` (stdio).
   b. In a Claude session: run `/setup` (real profile), `/hunt` on `reed` or
      `infojobs`, pick a REAL posting you genuinely want to apply to,
      `/review` → approve it, `/apply` → draft + coverage-check the materials.
   c. `start_application(finding_id)` — Claude executes the steps in YOUR
      browser: navigates the apply page, fills the fields, uploads via
      get_asset_file, resolves screeners (confirm each ask_user answer).
   d. At the review step Claude shows you the filled form and calls
      `request_submit` → expect `decision: await_human`.
   e. YOU click Submit on the employer's page. Tell Claude; it calls
      `confirm_submitted(application_id, evidence)`.

3. **Expected result / pass-fail:** application row reaches `submitted`;
   `check_seen` on the posting URL returns `applied: true`; the employer's
   confirmation (page/email) exists; the audit trail shows
   start → progress reports → request_submit → confirm_submitted in order.
   FAIL if Claude ever clicks Submit itself, or any tool response contains a
   submit instruction before `request_submit`.

4. **Risks:** a real application lands with a real employer — pick a posting
   you actually want. No money involved; the action is not retractable.

5. **What the agent already verified:** the entire loop end-to-end on both
   backends through the MCP tools with a fresh-connection persistence check
   (246 tests, incl. the consent-gate structural tests, RLS isolation live,
   obstacle pause/resume, dedup ledger write).
