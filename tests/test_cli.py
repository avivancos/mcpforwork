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
