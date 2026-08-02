"""`mcpforwork connect` formatters (S6.7) — pure str → str config blocks for
each supported agent client, in both run modes. Print-only, stdlib only.

- `local`   → stdio: `uvx --from mcpforwork mcpforwork-mcp`
- `compose` → streamable-HTTP at http://localhost:8500/mcp (single-tenant —
  the networked MCP shares the one local user; multi-tenant HTTP auth is
  hosted scope, ADR 0006).
"""

from __future__ import annotations

import json

CLIENTS = ("claude-code", "claude-desktop", "cursor", "codex", "opencode")
MODES = ("local", "compose")

_UVX_ARGS = ["--from", "mcpforwork", "mcpforwork-mcp"]
_HTTP_URL = "http://localhost:8500/mcp"
_CAVEAT = (
    "# Single-tenant: the compose MCP endpoint shares the one local user "
    "(ADR 0006).\n# Multi-tenant HTTP auth is hosted-track scope."
)

_HEADERS = {
    "claude-code": "=== claude-code — .mcp.json (project root) ===",
    "claude-desktop": "=== claude-desktop — claude_desktop_config.json ===",
    "cursor": "=== cursor — .cursor/mcp.json (project root) ===",
    "codex": "=== codex — ~/.codex/config.toml ===",
    "opencode": "=== opencode — opencode.json (project root) ===",
}

_DESKTOP_PATHS = (
    "# macOS:   ~/Library/Application Support/Claude/claude_desktop_config.json\n"
    "# Windows: %APPDATA%\\Claude\\claude_desktop_config.json"
)


def _json_block(servers: dict) -> str:
    return json.dumps({"mcpServers": servers}, indent=2)


def _local_json() -> str:
    return _json_block({"mcpforwork": {"command": "uvx", "args": _UVX_ARGS}})


def _compose_json() -> str:
    return _json_block({"mcpforwork": {"type": "http", "url": _HTTP_URL}})


def _codex_local() -> str:
    args = ", ".join(json.dumps(a) for a in _UVX_ARGS)
    return f'[mcp_servers.mcpforwork]\ncommand = "uvx"\nargs = [{args}]'


def _codex_compose() -> str:
    return f'[mcp_servers.mcpforwork]\nurl = "{_HTTP_URL}"'


def _opencode_local() -> str:
    return json.dumps(
        {"mcp": {"mcpforwork": {"type": "local", "command": ["uvx", *_UVX_ARGS]}}},
        indent=2,
    )


def _opencode_compose() -> str:
    return json.dumps(
        {"mcp": {"mcpforwork": {"type": "remote", "url": _HTTP_URL}}},
        indent=2,
    )


_BODIES = {
    ("claude-code", "local"): _local_json,
    ("claude-code", "compose"): _compose_json,
    ("claude-desktop", "local"): _local_json,
    ("claude-desktop", "compose"): _compose_json,
    ("cursor", "local"): _local_json,
    ("cursor", "compose"): _compose_json,
    ("codex", "local"): _codex_local,
    ("codex", "compose"): _codex_compose,
    ("opencode", "local"): _opencode_local,
    ("opencode", "compose"): _opencode_compose,
}


def render(client: str, mode: str) -> str:
    """The full block for one client+mode: header, body, and the mode-specific
    annotations (desktop config paths; compose tenancy caveat)."""
    if client not in CLIENTS:
        raise ValueError(f"unknown client {client!r} — choose from {', '.join(CLIENTS)}")
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r} — choose from {', '.join(MODES)}")
    parts = [_HEADERS[client]]
    if client == "claude-desktop":
        parts.append(_DESKTOP_PATHS)
    parts.append(_BODIES[(client, mode)]())
    if mode == "compose":
        parts.append(_CAVEAT)
    return "\n".join(parts)


def render_all(mode: str) -> str:
    """Every client's block for one mode, separated by blank lines."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r} — choose from {', '.join(MODES)}")
    return "\n\n".join(render(client, mode) for client in CLIENTS)
