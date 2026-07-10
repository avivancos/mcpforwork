"""Driving entrypoints — all thin (auth + serialization only).

mcp (FastMCP stdio + streamable HTTP), api (FastAPI), cli (Typer). Business
rules live in services; an entrypoint that grows logic is a boundary
violation. Entrypoints never import each other.
"""
