"""S4 MCP tools end-to-end over a real tmp DB — persistence proven on FRESH
connections so a commit-dropping tool cannot pass (the S3 lesson)."""

import json

from mcpforwork.adapters.db import connect
from mcpforwork.entrypoints.mcp import server

_POSTING = {"url": "https://x.com/jobs/1", "title": "Data Engineer", "description": "Python."}


def _approved_match() -> int:
    server.update_profile(
        {"full_name": "Ada", "contact_email": "ada@x.com", "target_titles": ["Data Engineer"]}
    )
    server.submit_findings("weworkremotely", [_POSTING])
    fid = json.loads(server.list_matches(0))["matches"][0]["id"]
    server.approve_match(fid)
    return fid


def _fresh_value(db_url: str, sql: str, params: tuple):
    fresh = connect(db_url)
    try:
        return fresh.fetchone(sql, params)
    finally:
        fresh.close()


def test_full_supervised_apply_flow_through_the_tools(mcp_env) -> None:
    fid = _approved_match()

    session = json.loads(server.start_application(fid))
    app_id = session["application_id"]
    # Persisted (fresh connection).
    assert (
        _fresh_value(mcp_env, "SELECT state FROM applications WHERE id = ?", (app_id,))["state"]
        == "filling"
    )

    # Walk the plan; an unknown screener question goes through resolve_field.
    q = json.loads(server.resolve_field(app_id, "Notice period"))
    assert q["ask_user"] is True
    server.save_form_answer("Notice period", "1 month")
    assert json.loads(server.resolve_field(app_id, "Notice period"))["answer"] == "1 month"
    for step in session["steps"]:
        last = json.loads(server.report_apply_progress(app_id, step["step_id"], "ok"))
    assert last["state"] == "awaiting_human"

    decision = json.loads(server.request_submit(app_id, "form shown to the human"))
    assert decision["decision"] == "await_human"
    assert (
        _fresh_value(mcp_env, "SELECT state FROM applications WHERE id = ?", (app_id,))["state"]
        == "submit_requested"
    )

    confirmed = json.loads(server.confirm_submitted(app_id, "confirmation page"))
    assert confirmed["ok"] is True
    assert (
        _fresh_value(mcp_env, "SELECT state FROM applications WHERE id = ?", (app_id,))["state"]
        == "submitted"
    )
    # Dedup ledger written (fresh connection) — the posting never re-surfaces.
    assert (
        _fresh_value(mcp_env, "SELECT id FROM external_applications WHERE finding_id = ?", (fid,))
        is not None
    )

    outcome = json.loads(server.record_outcome(app_id, "interview", "phone screen"))
    assert outcome["ok"] is True
    assert (
        _fresh_value(mcp_env, "SELECT outcome FROM applications WHERE id = ?", (app_id,))["outcome"]
        == "interview"
    )

    report = json.loads(server.report_playbook_result("weworkremotely", "success", {"ok": 1}))
    assert report["ok"] is True
    assert (
        _fresh_value(
            mcp_env, "SELECT id FROM playbook_reports WHERE id = ?", (report["report_id"],)
        )
        is not None
    )


def test_apply_tool_error_paths_return_error(mcp_env) -> None:
    _approved_match()
    assert "error" in json.loads(server.start_application(9999))
    assert "error" in json.loads(server.report_apply_progress(9999, 1, "ok"))
    assert "error" in json.loads(server.request_submit(9999))
    assert "error" in json.loads(server.confirm_submitted(9999))
    assert "error" in json.loads(server.record_outcome(9999, "interview"))
    assert "error" in json.loads(server.get_asset_file(9999))
    assert "error" in json.loads(server.report_playbook_result("nope", "drift", {}))
