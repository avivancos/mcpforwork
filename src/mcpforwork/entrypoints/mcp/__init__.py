"""MCP entrypoint — FastMCP server over stdio (self-host) / streamable HTTP.

The product's primary interface. Thin: tools open a tenant-scoped UnitOfWork,
call a service, and return JSON with a next_action breadcrumb.
"""
