"""Profile MCP tools driven over a real tmp DB — no mocks."""

import json

from mcpforwork.adapters.db import connect
from mcpforwork.entrypoints.mcp import server
from mcpforwork.services import profiles

# mcp_env fixture is in conftest.py — points the tools' _uow() at a tmp SQLite DB.


def test_update_creates_the_active_profile_when_none_exists(mcp_env) -> None:
    result = json.loads(
        server.update_profile({"full_name": "Ada", "target_titles": ["Backend Engineer"]})
    )
    assert result["ok"] is True
    got = json.loads(server.get_profile())
    assert got["profile"]["full_name"] == "Ada"
    assert got["profile"]["target_titles"] == ["Backend Engineer"]
    assert got["next_action"]


def test_get_profile_before_setup_returns_error(mcp_env) -> None:
    assert "error" in json.loads(server.get_profile())


def test_update_validation_error_returns_error_not_raise(mcp_env) -> None:
    assert "error" in json.loads(server.update_profile({"seniority": "wizard"}))


def test_list_and_set_active_profile(mcp_env) -> None:
    server.update_profile({"full_name": "Ada"})  # profile 1 (active)
    first = json.loads(server.get_profile())["profile"]["id"]
    second = json.loads(server.create_profile({"full_name": "Ada Data"}, label="data"))[
        "profile_id"
    ]

    listed = json.loads(server.list_profiles())["profiles"]
    assert {p["id"] for p in listed} == {first, second}
    assert json.loads(server.get_profile())["profile"]["id"] == second  # newest is active

    server.set_active_profile(first)
    assert json.loads(server.get_profile())["profile"]["id"] == first


def test_add_achievements_and_set_style_on_active_profile(mcp_env) -> None:
    server.update_profile({"full_name": "Ada"})
    r = json.loads(server.add_achievements([{"metric": "Cut latency 40%", "role": "Lead"}]))
    assert r["ok"] is True
    server.set_style_profile("Dear team, ...", {"tone": "warm"})
    prof_id = json.loads(server.get_profile())["profile"]["id"]
    # Verify persisted via the service on a fresh connection to the same DB.
    uow = connect(mcp_env)
    try:
        assert [a["metric"] for a in profiles.list_achievements(uow, 1, prof_id)] == [
            "Cut latency 40%"
        ]
        assert profiles.get_style_profile(uow, 1, prof_id)["directives"] == {"tone": "warm"}
    finally:
        uow.close()


def test_add_achievements_to_a_foreign_profile_returns_error(mcp_env) -> None:
    server.update_profile({"full_name": "Ada"})
    # profile id 999 does not belong to the local user.
    assert "error" in json.loads(server.add_achievements([{"metric": "x"}], profile_id=999))


def test_import_from_url_findings_applies_fields_and_audits_source(mcp_env) -> None:
    server.update_profile({"full_name": "Ada"})
    result = json.loads(
        server.import_from_url_findings(
            "https://linkedin.com/in/ada", {"city": "London", "sectors": ["fintech"]}
        )
    )
    assert result["profile"]["city"] == "London"
    assert result["source"] == "https://linkedin.com/in/ada"
    uow = connect(mcp_env)
    try:
        audit = uow.fetchone(
            "SELECT detail FROM audit_log WHERE action = 'import_from_url_findings'"
        )
        assert "linkedin.com/in/ada" in audit["detail"]
    finally:
        uow.close()


_LINKEDIN_PAGE = """Ada Lovelace
ada@example.com
https://www.linkedin.com/in/ada

About
Remote freelance Python / LLM engineer. Open to B2B invoice work.

Experience
Built agentic MCP tools with FastAPI and Docker.
"""


def test_preview_url_import_returns_hints_and_never_writes(mcp_env) -> None:
    # S5.4: LinkedIn path is preview (read-only) → CONFIRM → import_from_url_findings.
    result = json.loads(
        server.preview_url_import("https://www.linkedin.com/in/ada", _LINKEDIN_PAGE)
    )
    assert result["source_url"] == "https://www.linkedin.com/in/ada"
    assert result["candidate"]["full_name"] == "Ada Lovelace"
    assert result["candidate"]["contact_email"] == "ada@example.com"
    hints = result["setup_hints"]
    assert "remote" in hints["work_modes"]
    assert "freelance" in hints["employment_types"]
    assert "python" in hints["skills_top"]
    assert any("b2b" in s.lower() or "invoice" in s.lower() for s in hints["signals"])
    assert result["cv_text"] == _LINKEDIN_PAGE
    assert "confirm" in result["next_action"].lower()
    # Must not have created/updated a profile.
    assert "error" in json.loads(server.get_profile())


def test_preview_url_import_rejects_non_https(mcp_env) -> None:
    assert "error" in json.loads(
        server.preview_url_import("http://linkedin.com/in/ada", _LINKEDIN_PAGE)
    )
    assert "error" in json.loads(server.preview_url_import("javascript:alert(1)", _LINKEDIN_PAGE))
    assert "error" in json.loads(server.preview_url_import("data:text/html,hi", _LINKEDIN_PAGE))


def test_preview_url_import_rejects_oversized_page_text(mcp_env) -> None:
    assert "error" in json.loads(
        server.preview_url_import("https://www.linkedin.com/in/ada", "x" * 300_000)
    )
