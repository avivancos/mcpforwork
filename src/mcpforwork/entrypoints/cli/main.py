"""`mcpforwork` CLI: init / serve / version (stdlib argparse — no CLI framework)."""

from __future__ import annotations

import argparse
import importlib.metadata
import sys
from urllib.parse import urlsplit, urlunsplit

from mcpforwork import config
from mcpforwork.adapters.db import connect
from mcpforwork.entrypoints.cli import connect as connect_cmd


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


def _init() -> int:
    """Create the data dir, migrate the self-host SQLite db, print the connector snippet."""
    config.data_dir().mkdir(parents=True, exist_ok=True)
    uow = connect(config.db_url())
    uow.close()
    print(f"Initialized {_redact(config.db_url())}")
    print("\nAdd the connector to Claude Code / Desktop (.mcp.json):\n")
    # Single source of truth: the same block `connect --client claude-code` prints.
    print(connect_cmd.render("claude-code", "local").split("\n", 1)[1])
    print("\nOther clients (Cursor, Codex, OpenCode) or compose mode:")
    print("  mcpforwork connect                 # all clients, local stdio")
    print("  mcpforwork connect --mode compose  # HTTP against docker compose")
    print("\nThen run /setup in your client to build your profile (< 3 minutes).")
    return 0


def _serve(run=None) -> int:
    """Run the stdio MCP server (the sanctioned cli -> mcp launcher edge). `run`
    is injectable so dispatch is testable without launching the blocking loop."""
    if run is None:
        from mcpforwork.entrypoints.mcp.server import main as run
    run()
    return 0


def _version() -> int:
    try:
        print(importlib.metadata.version("mcpforwork"))
    except importlib.metadata.PackageNotFoundError:  # pragma: no cover
        print("unknown")
    return 0


def _connect(client: str | None, mode: str) -> int:
    """Print the MCP client config block(s). Print-only — never writes the
    user's config files (their editor, their paste)."""
    try:
        out = connect_cmd.render_all(mode) if client is None else connect_cmd.render(client, mode)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(out)
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
    connect_parser = sub.add_parser(
        "connect", help="print the MCP client config for your agent client"
    )
    connect_parser.add_argument("--client", choices=connect_cmd.CLIENTS, default=None)
    connect_parser.add_argument("--mode", choices=connect_cmd.MODES, default="local")
    args = parser.parse_args(argv)
    if args.command == "init":
        return _init()
    if args.command == "serve":
        return _serve()
    if args.command == "version":
        return _version()
    if args.command == "connect":
        return _connect(args.client, args.mode)
    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
