from __future__ import annotations

import pytest
from typer.testing import CliRunner

from server.app.cli.main import app

runner = CliRunner()


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

    def run(app: object, *, host: str, port: int, log_config: None) -> None:
        calls.update(app=app, host=host, port=port, log_config=log_config)

    monkeypatch.setattr("server.app.cli.server.uvicorn.run", run)
    result = runner.invoke(app, ["server", "--host", "0.0.0.0", "--port", "9000"])

    assert result.exit_code == 0, result.output
    assert calls["host"] == "0.0.0.0"
    assert calls["port"] == 9000
    assert calls["log_config"] is None
