from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from typer.testing import CliRunner

from server.app.cli.main import app

runner = CliRunner()


def _record_migrations(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Capture the engines handed to the migration helper."""
    engines: list[object] = []

    def apply(engine: object, revision: str = "head", **_: object) -> None:
        engines.append(engine)

    monkeypatch.setattr("server.app.cli.server.apply_migrations", apply)
    return engines


def _silence_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    def run(*_: object, **__: object) -> None:
        return None

    monkeypatch.setattr("server.app.cli.server.uvicorn.run", run)


def test_server_command_upgrades_the_database_before_serving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engines = _record_migrations(monkeypatch)
    _silence_uvicorn(monkeypatch)

    result = runner.invoke(app, ["server", "--upgrade-db"])

    assert result.exit_code == 0, result.output
    assert len(engines) == 1
    assert isinstance(engines[0], AsyncEngine)


def test_server_command_skips_migrations_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engines = _record_migrations(monkeypatch)
    _silence_uvicorn(monkeypatch)

    result = runner.invoke(app, ["server", "--port", "9000"])

    assert result.exit_code == 0, result.output
    assert engines == []


def test_server_command_upgrades_before_reload_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engines = _record_migrations(monkeypatch)
    _silence_uvicorn(monkeypatch)

    result = runner.invoke(app, ["server", "--reload", "--upgrade-db"])

    assert result.exit_code == 0, result.output
    assert len(engines) == 1


def test_server_command_supports_reload_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def run(app: object, **options: object) -> None:
        calls.update(app=app, **options)

    monkeypatch.setattr("server.app.cli.server.uvicorn.run", run)
    result = runner.invoke(app, ["server", "--reload"])

    assert result.exit_code == 0, result.output
    assert calls["app"] == "server.app.http.app:create_app"
    assert calls["factory"] is True
    assert calls["reload"] is True


def test_server_command_passes_host_and_port_to_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def run(app: object, **options: object) -> None:
        calls.update(app=app, **options)

    monkeypatch.setattr("server.app.cli.server.uvicorn.run", run)
    result = runner.invoke(app, ["server", "--host", "0.0.0.0", "--port", "9000"])

    assert result.exit_code == 0, result.output
    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 9000
    assert calls["log_config"] is None
