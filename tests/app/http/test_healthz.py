from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.app.bootstrap import AppConfig, create_container
from server.app.http import create_app


def test_healthz_reads_the_container_from_app_state(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = AppConfig.model_validate(
        {"app": {"name": "test"}, "logging": {"colors": False}}
    )
    container = create_container(config)
    app = create_app(container)

    assert app.state.container is container
    with TestClient(app) as client:
        response = client.get(
            "/healthz",
            headers={"x-request-id": "request-1", "x-correlation-id": "trace-1"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "register_enabled": True,
        "register_skip_verify": True,
        "token_header": "X-Bearer-Token",
        "identity_providers": {
            "local": {"enabled": True},
            "databricksapps": {
                "enabled": True,
                "headers": {
                    "email": "X-Forwarded-Email",
                    "access_token": "X-Forwarded-Access-Token",
                },
            },
        },
        "password_policy": {
            "min_length": 12,
            "require_upper": True,
            "require_digit": True,
            "require_symbol": True,
        },
    }
    output = capsys.readouterr().out
    assert "http.request.started" in output
    assert "http.request.finished" in output
    assert "http_request_id='request-1'" in output
    assert "correlation_id='trace-1'" in output
    assert "method='GET'" in output
    assert "path='/healthz'" in output
    assert "status_code=200" in output
