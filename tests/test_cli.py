"""CLI init/serve/version (S5.3) — the self-host front door."""

from pathlib import Path

from mcpforwork.adapters.db import connect
from mcpforwork.adapters.db.migrations import SCHEMA_VERSION
from mcpforwork.entrypoints.cli.main import main


def test_init_creates_a_migrated_db_and_prints_the_snippet(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setenv("MCPFORWORK_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("MCPFORWORK_DB_URL", raising=False)
    assert main(["init"]) == 0
    out = capsys.readouterr().out
    assert "mcpforwork-mcp" in out  # the .mcp.json connector snippet
    db = tmp_path / "data" / "mcpforwork.db"
    assert db.is_file()
    uow = connect(f"sqlite:///{db}")
    try:
        assert uow.fetchone("PRAGMA user_version")["user_version"] == SCHEMA_VERSION
    finally:
        uow.close()


def test_init_is_idempotent(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MCPFORWORK_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("MCPFORWORK_DB_URL", raising=False)
    assert main(["init"]) == 0
    assert main(["init"]) == 0  # second run: no error


def test_version_prints_the_package_version(capsys):
    assert main(["version"]) == 0
    assert capsys.readouterr().out.strip()


def test_no_args_shows_usage(capsys):
    assert main([]) == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_help_exits_zero(capsys):
    # argparse --help exits 0 via SystemExit; the serve/init/version subcommands
    # must appear in the help so the shipped commands are discoverable.
    import pytest

    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    help_text = capsys.readouterr().out
    assert "serve" in help_text and "init" in help_text


def test_serve_dispatch_target_is_importable() -> None:
    # `serve` delegates to the MCP server's main; a rename would break the
    # shipped `mcpforwork serve` command (import-linter checks module edges, not
    # symbols). Pin the symbol.
    from mcpforwork.entrypoints.mcp.server import main as mcp_main

    assert callable(mcp_main)


def test_init_redacts_a_postgres_password(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MCPFORWORK_DB_URL", "sqlite:///" + str(tmp_path / "d.db"))
    from mcpforwork.entrypoints.cli.main import _redact

    masked = _redact("postgres://appuser:supersecret@db.internal:5432/mcpforwork")
    assert "supersecret" not in masked
    assert "appuser" in masked and "db.internal" in masked
