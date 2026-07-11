"""HTTP parity API (Starlette) — the driving adapter the web dashboard reads.

A thin layer: authenticate via the magic-link session cookie, then delegate to
the same services the MCP tools use. It never re-implements domain logic and,
like every entrypoint, imports no other entrypoint.
"""
