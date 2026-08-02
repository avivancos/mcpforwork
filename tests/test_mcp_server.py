"""FastMCP stdio entrypoint — real in-memory server, no mocks."""

import asyncio
import json
from pathlib import Path

from mcpforwork.entrypoints.mcp import guidance, server


def test_list_tools_registers_server_info() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    assert "server_info" in {t.name for t in tools}


def test_server_info_reports_version_tools_and_invariants() -> None:
    payload = json.loads(server.server_info())
    assert payload["name"] == "mcpforwork"
    assert "server_info" in payload["tools"]
    assert payload["invariants"]  # the load-bearing invariants are surfaced
    assert payload["next_action"]  # every response carries a breadcrumb


def test_every_registered_tool_has_a_next_action_breadcrumb() -> None:
    tools = asyncio.run(server.mcp.list_tools())
    missing = sorted(t.name for t in tools if not guidance.next_action(t.name))
    assert missing == []


def test_server_instructions_state_the_consent_and_zero_llm_invariants() -> None:
    text = guidance.SERVER_INSTRUCTIONS.lower()
    assert "never auto-submit" in text
    assert "never fetches" in text or "never browses" in text or "server never" in text


def test_server_instructions_describe_the_shipped_apply_loop() -> None:
    # S6.5: guidance must not claim assets/apply "arrive in later sprints".
    text = guidance.SERVER_INSTRUCTIONS
    lowered = text.lower()
    assert "later sprint" not in lowered
    assert "later version" not in lowered
    assert "start_application" in text
    assert "request_submit" in text
    assert "confirm_submitted" in text
    assert "/apply" in text or "/review" in text


def test_setup_prompt_is_cv_first_and_uses_setup_hints() -> None:
    # S5.3: paste CV → parse_cv → confirm contact + hints → propose focus → persist.
    # S5.4: LinkedIn/URL → preview_url_import → CONFIRM → import_from_url_findings.
    prompt = server.setup_session()
    lowered = prompt.lower()
    assert "parse_cv" in lowered
    assert "setup_hints" in lowered
    assert "confirm" in lowered
    assert "update_profile" in lowered
    assert "profile_gaps" in lowered
    assert "preview_url_import" in lowered
    assert "import_from_url_findings" in lowered
    # CV-first: parse_cv appears before profile_gaps in the orchestration.
    assert lowered.index("parse_cv") < lowered.index("profile_gaps")
    assert "never invent" in lowered
    # SERVER_INSTRUCTIONS must also say CV-first / setup_hints.
    instr = guidance.SERVER_INSTRUCTIONS.lower()
    assert "cv-first" in instr or "parse_cv" in instr
    assert "setup_hints" in instr or "setup_hints" in guidance.next_action("parse_cv").lower()
    assert "preview_url_import" in instr
    assert "confirm" in guidance.next_action("preview_url_import").lower()


def test_apply_prompt_covers_the_full_orchestration_loop() -> None:
    prompt = server.apply_session()
    lowered = prompt.lower()
    assert "later sprint" not in lowered
    assert "later version" not in lowered
    assert "get_generation_brief" in prompt
    assert "ats_coverage_check" in prompt
    assert "start_application" in prompt
    assert "report_apply_progress" in prompt
    assert "request_submit" in prompt
    assert "confirm_submitted" in prompt
    assert "human" in lowered
    assert "clicks submit" in lowered or "never click submit" in lowered
    # S7.2c: fill-plan quirks from apply_playbook must stay in the prompt.
    assert "quirks" in lowered
    assert "apply_playbook" in lowered or "fill plan" in lowered


def test_hunt_guidance_tells_the_client_to_use_the_search_box_when_mode_says_so() -> None:
    # S2.6: surfacing `mode` is inert unless the client is instructed to branch on
    # it — the hunt breadcrumbs and SERVER_INSTRUCTIONS must mention search_box.
    assert "search_box" in guidance.next_action("hunt_plan")
    assert "search_box" in guidance.next_action("source_playbook")
    assert "search_box" in guidance.SERVER_INSTRUCTIONS


def test_uow_opens_a_tenant_scoped_handle_and_seeds_the_local_user(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("MCPFORWORK_DB_URL", f"sqlite:///{tmp_path / 'u.db'}")
    monkeypatch.setenv("MCPFORWORK_USER_ID", "1")
    uow, user_id = server._uow()
    try:
        assert user_id == 1
        row = uow.fetchone("SELECT email FROM users WHERE id = ?", (user_id,))
        assert row["email"] == "local@self-host"
    finally:
        uow.close()


def test_uow_local_user_is_idempotent_across_calls(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MCPFORWORK_DB_URL", f"sqlite:///{tmp_path / 'u.db'}")
    first_uow, _ = server._uow()
    first_uow.close()
    second_uow, _ = server._uow()  # must not raise on the existing user row
    try:
        count = second_uow.fetchone("SELECT COUNT(*) AS n FROM users")
        assert count["n"] == 1
    finally:
        second_uow.close()
