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
