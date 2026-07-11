# mcpfor.work — Python self-host / MCP server image (ADR 0003).
# Built on the official uv image (bundles a matching CPython), so the resolved
# virtualenv's interpreter is guaranteed present at runtime — no cross-base
# interpreter mismatch. `--no-editable` installs the project (incl. packs/*.yaml
# data) into the venv so the image is self-contained.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

# Project metadata + sources needed to resolve the lock and build the wheel
# (hatchling reads the version from src/mcpforwork/__init__.py and the readme).
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

ENV PATH="/app/.venv/bin:$PATH" \
    MCPFORWORK_DATA_DIR=/data

# Unprivileged runtime; /data holds the self-host SQLite db (mounted volume).
RUN useradd -r -u 1001 app && mkdir -p /data && chown app:app /data
USER app

# Default: stdio MCP (works with `docker run -i` and .mcpb-style clients).
# docker-compose runs it over streamable-http as a networked connector
# (see the `command:` override there; :8500 in the compose demo).
EXPOSE 8500
CMD ["mcpforwork-mcp"]
