"""`mcpforwork connect` (S6.7) — agent-client config generator.

Golden-output tests: the full emitted block is asserted verbatim (config
drift must fail loudly), and every JSON/TOML block is parsed to prove it is
valid in the client's native format.
"""

import json
import tomllib

from mcpforwork.entrypoints.cli.connect import CLIENTS, MODES, render
from mcpforwork.entrypoints.cli.main import main

_LOCAL_JSON = {
    "mcpServers": {
        "mcpforwork": {"command": "uvx", "args": ["--from", "mcpforwork", "mcpforwork-mcp"]}
    }
}
_COMPOSE_JSON = {"mcpServers": {"mcpforwork": {"type": "http", "url": "http://localhost:8500/mcp"}}}
_CAVEAT = (
    "# Single-tenant: the compose MCP endpoint shares the one local user "
    "(ADR 0006).\n# Multi-tenant HTTP auth is hosted-track scope."
)


def test_every_client_and_mode_is_covered():
    assert set(CLIENTS) == {"claude-code", "claude-desktop", "cursor", "codex", "opencode"}
    assert set(MODES) == {"local", "compose"}


def test_claude_code_local_golden():
    assert render("claude-code", "local") == (
        "=== claude-code — .mcp.json (project root) ===\n" + json.dumps(_LOCAL_JSON, indent=2)
    )


def test_claude_desktop_local_golden_includes_the_config_path():
    out = render("claude-desktop", "local")
    assert out.startswith("=== claude-desktop — claude_desktop_config.json ===\n")
    assert json.dumps(_LOCAL_JSON, indent=2) in out
    # The user must know WHERE the file lives — both OS paths are printed.
    assert "Library/Application Support/Claude" in out
    assert "%APPDATA%" in out


def test_cursor_local_golden():
    assert render("cursor", "local") == (
        "=== cursor — .cursor/mcp.json (project root) ===\n" + json.dumps(_LOCAL_JSON, indent=2)
    )


def test_codex_local_golden_is_valid_toml():
    out = render("codex", "local")
    assert out.startswith("=== codex — ~/.codex/config.toml ===\n")
    block = out.split("\n", 1)[1]
    parsed = tomllib.loads(block)
    assert parsed["mcp_servers"]["mcpforwork"]["command"] == "uvx"
    assert parsed["mcp_servers"]["mcpforwork"]["args"] == [
        "--from",
        "mcpforwork",
        "mcpforwork-mcp",
    ]


def test_opencode_local_golden():
    out = render("opencode", "local")
    assert out.startswith("=== opencode — opencode.json (project root) ===\n")
    block = json.loads(out.split("\n", 1)[1])
    assert block["mcp"]["mcpforwork"]["type"] == "local"
    assert block["mcp"]["mcpforwork"]["command"] == [
        "uvx",
        "--from",
        "mcpforwork",
        "mcpforwork-mcp",
    ]


def test_compose_mode_points_at_the_http_endpoint_with_the_tenancy_caveat():
    for client in CLIENTS:
        out = render(client, "compose")
        assert "http://localhost:8500/mcp" in out, client
        assert _CAVEAT in out, client  # ADR 0006 single-tenant caveat
        assert "uvx" not in out, client  # compose mode never launches stdio


def test_compose_json_clients_emit_http_type():
    for client in ("claude-code", "claude-desktop", "cursor"):
        out = render(client, "compose")
        assert json.dumps(_COMPOSE_JSON, indent=2) in out, client


def test_codex_compose_golden_is_valid_toml():
    out = render("codex", "compose")
    assert out.startswith("=== codex — ~/.codex/config.toml ===\n")
    block = out.split("\n", 1)[1].split("# Single-tenant")[0]
    parsed = tomllib.loads(block)
    assert parsed["mcp_servers"]["mcpforwork"]["url"] == "http://localhost:8500/mcp"


def test_opencode_compose_golden():
    out = render("opencode", "compose")
    assert out.startswith("=== opencode — opencode.json (project root) ===\n")
    block = json.loads(out.split("\n", 1)[1].split("# Single-tenant")[0])
    assert block["mcp"]["mcpforwork"]["type"] == "remote"
    assert block["mcp"]["mcpforwork"]["url"] == "http://localhost:8500/mcp"


def test_local_mode_never_carries_the_caveat_or_url():
    for client in CLIENTS:
        out = render(client, "local")
        assert "localhost:8500" not in out, client
        assert _CAVEAT not in out, client


def test_every_emitted_json_block_parses():
    for client in ("claude-code", "claude-desktop", "cursor", "opencode"):
        for mode in MODES:
            out = render(client, mode)
            start = out.index("{")
            # JSON block runs to the last closing brace in the output.
            json.loads(out[start : out.rindex("}") + 1])


def test_unknown_client_or_mode_is_rejected():
    for bad in ("vscode", "emacs"):
        try:
            render(bad, "local")
            raise AssertionError("expected ValueError")
        except ValueError:
            pass
    try:
        render("cursor", "remote")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_cli_connect_prints_all_clients_without_a_flag(capsys):
    assert main(["connect"]) == 0
    out = capsys.readouterr().out
    for client in CLIENTS:
        assert f"=== {client} " in out


def test_cli_connect_single_client_and_compose_mode(capsys):
    assert main(["connect", "--client", "cursor", "--mode", "compose"]) == 0
    out = capsys.readouterr().out
    assert "=== cursor " in out
    assert "claude-code" not in out
    assert "http://localhost:8500/mcp" in out


def test_cli_connect_rejects_an_unknown_client(capsys):
    # argparse validates --client choices itself: SystemExit(2) + stderr.
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["connect", "--client", "vscode"])
    assert exc.value.code == 2
    assert "vscode" in capsys.readouterr().err


def test_init_points_at_connect(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MCPFORWORK_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("MCPFORWORK_DB_URL", raising=False)
    assert main(["init"]) == 0
    assert "mcpforwork connect" in capsys.readouterr().out
