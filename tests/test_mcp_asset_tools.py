"""S3 MCP tools driven end-to-end over a real tmp DB (brief -> asset -> coverage
-> review -> record). Persistence is verified on a FRESH connection so a
commit-dropping tool cannot pass."""

import json
import re

from mcpforwork.adapters.db import connect
from mcpforwork.entrypoints.mcp import server

_POSTING = {
    "url": "https://x.com/jobs/1",
    "title": "Data Engineer",
    "description": "Python and SQL pipelines. Databricks required. Airflow a plus.",
}


def _seed() -> int:
    server.update_profile(
        {"target_titles": ["Data Engineer"], "cv_text": "Python, SQL, Airflow at Acme."}
    )
    server.submit_findings("weworkremotely", [_POSTING])
    return json.loads(server.list_matches(0))["matches"][0]["id"]


def test_full_apply_flow_through_the_tools(mcp_env) -> None:
    fid = _seed()
    assert json.loads(server.approve_match(fid))["status"] == "approved"
    # Persisted on a fresh connection (kills a commit-dropping approve tool).
    fresh = connect(mcp_env)
    try:
        assert (
            fresh.fetchone("SELECT status FROM explore_findings WHERE id = ?", (fid,))["status"]
            == "approved"
        )
    finally:
        fresh.close()

    brief = json.loads(server.get_generation_brief(fid, "cover_letter"))
    assert "databricks" in brief["job"]["keywords"]

    submitted = json.loads(server.submit_asset(fid, "cover_letter", "I use Python and SQL."))
    assert submitted["version"] == 1

    # Persistence proven on a fresh connection (kills a dropped commit).
    fresh = connect(mcp_env)
    try:
        row = fresh.fetchone(
            "SELECT content FROM generated_assets WHERE id = ?", (submitted["asset_id"],)
        )
        assert row is not None and "Python" in row["content"]
    finally:
        fresh.close()

    listed = json.loads(server.get_assets(fid))
    assert listed["count"] == 1

    cov = json.loads(server.ats_coverage_check(fid, submitted["asset_id"]))
    assert "databricks" in cov["genuine_gaps"]
    assert "airflow" in cov["missing_but_have"]

    recorded = json.loads(server.record_application(_POSTING["url"], channel="web"))
    assert recorded["ok"] is True
    # Recorded on a fresh connection too, and linked to the finding.
    fresh = connect(mcp_env)
    try:
        assert (
            fresh.fetchone("SELECT id FROM external_applications WHERE finding_id = ?", (fid,))
            is not None
        )
    finally:
        fresh.close()


def test_tool_error_paths_return_error_not_raise(mcp_env) -> None:
    fid = _seed()
    assert "error" in json.loads(server.get_generation_brief(9999, "cv"))
    assert "error" in json.loads(server.submit_asset(fid, "poem", "x"))
    assert "error" in json.loads(server.ats_coverage_check(fid, 9999))
    assert "error" in json.loads(server.approve_match(9999))
    assert "error" in json.loads(server.discard_match(9999))


def test_discard_tool_persists_and_audits_reason(mcp_env) -> None:
    fid = _seed()
    json.loads(server.discard_match(fid, reason="not remote"))
    fresh = connect(mcp_env)
    try:
        status = fresh.fetchone("SELECT status FROM explore_findings WHERE id = ?", (fid,))
        assert status["status"] == "discarded"
        audit = fresh.fetchone("SELECT detail FROM audit_log WHERE action = 'discard_match'")
        assert "not remote" in audit["detail"]
    finally:
        fresh.close()


def test_prompts_reference_only_registered_tools(mcp_env) -> None:
    tools = set(json.loads(server.server_info())["tools"])
    for prompt_fn in (
        server.setup_session,
        server.review_session,
        server.apply_session,
        server.hunt_session,
    ):
        # snake_case tokens followed by "(" are tool references; single prose
        # words like "sector(s)" are not.
        referenced = {t for t in re.findall(r"\b([a-z_]{4,})\(", prompt_fn()) if "_" in t}
        unknown = referenced - tools
        assert not unknown, f"{prompt_fn.__name__} references unregistered tools: {unknown}"
