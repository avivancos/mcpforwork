"""CLI entrypoint — self-host front door (init / serve / version).

Thin launcher: `serve` delegates to the MCP stdio server (the one sanctioned
cli -> mcp edge; see the import-linter contract note).
"""
