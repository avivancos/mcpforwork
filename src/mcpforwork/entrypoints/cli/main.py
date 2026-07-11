"""`mcpforwork` CLI: init / serve / version (stdlib argparse — no CLI framework)."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from urllib.parse import urlsplit, urlunsplit

from mcpforwork import config
from mcpforwork.adapters.db import connect


def _redact(url: str) -> str:
    """Mask any password before printing a DB URL to stdout (shell history, CI
    logs). SQLite URLs carry no secret and pass through unchanged."""
    parts = urlsplit(url)
    if not parts.password:
        return url
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{parts.username}:***@{host}{port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


_SNIPPET = {
    "mcpServers": {
        "mcpforwork": {"command": "uvx", "args": ["--from", "mcpforwork", "mcpforwork-mcp"]}
    }
}


def _init() -> int:
    """Create the data dir, migrate the self-host SQLite db, print the connector snippet."""
    config.data_dir().mkdir(parents=True, exist_ok=True)
    uow = connect(config.db_url())
    uow.close()
    print(f"Initialized {_redact(config.db_url())}")
    print("\nAdd the connector to Claude Code / Desktop (.mcp.json):\n")
    print(json.dumps(_SNIPPET, indent=2))
    print("\nThen run /setup in your client to build your profile (< 3 minutes).")
    return 0


def _serve() -> int:
    """Run the stdio MCP server (the sanctioned cli -> mcp launcher edge)."""
    from mcpforwork.entrypoints.mcp.server import main as mcp_main

    mcp_main()
    return 0


def _version() -> int:
    try:
        print(importlib.metadata.version("mcpforwork"))
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        print("unknown")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mcpforwork",
        description="Open-source, MCP-first job-search copilot (self-host).",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("init", help="create the local database and print the connector snippet")
    sub.add_parser("serve", help="run the MCP server over stdio")
    sub.add_parser("version", help="print the version")
    args = parser.parse_args(argv)
    if args.command == "init":
        return _init()
    if args.command == "serve":
        return _serve()
    if args.command == "version":
        return _version()
    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
