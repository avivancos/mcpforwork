"""Hunt MCP tools driven over a real tmp DB — the /hunt flow end to end."""

import json

from mcpforwork.entrypoints.mcp import server

# mcp_env fixture is in conftest.py.


def test_hunt_plan_submit_list_and_check_seen_flow(mcp_env) -> None:
    server.update_profile(
        {"target_titles": ["Data Engineer"], "sectors": ["tech"], "work_modes": ["remote"]}
    )
    plan = json.loads(server.hunt_plan())
    assert plan["count"] > 0
    slug = plan["sources"][0]["slug"]

    submitted = json.loads(
        server.submit_findings(
            slug,
            [
                {
                    "url": "https://example.com/jobs/1",
                    "title": "Senior Data Engineer",
                    "description": "Build data pipelines",
                }
            ],
        )
    )
    assert submitted["new"] == 1

    matches = json.loads(server.list_matches(1))["matches"]
    assert matches[0]["title"] == "Senior Data Engineer"
    finding_id = matches[0]["id"]
    assert json.loads(server.get_match(finding_id))["match"]["id"] == finding_id

    seen = json.loads(server.check_seen(["https://example.com/jobs/1"]))["items"]
    assert seen[0]["recommendation"] == "skip"


def test_hunt_plan_without_a_profile_returns_error(mcp_env) -> None:
    assert "error" in json.loads(server.hunt_plan())


def test_list_sources_tool_returns_the_seed_packs(mcp_env) -> None:
    result = json.loads(server.list_sources())
    assert result["count"] > 0
    assert any(s["slug"] == "remoteok" for s in result["sources"])


def test_source_playbook_tool(mcp_env) -> None:
    playbook = json.loads(server.source_playbook("remoteok", "data engineer"))
    assert playbook["slug"] == "remoteok"
    assert "data" in playbook["search_url"].lower()


def test_get_match_unknown_id_returns_error(mcp_env) -> None:
    server.update_profile({"target_titles": ["Data Engineer"]})
    assert "error" in json.loads(server.get_match(9999))
