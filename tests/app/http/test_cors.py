from __future__ import annotations

from fastapi.testclient import TestClient

from server.app.bootstrap import AppConfig, create_container
from server.app.http import create_app


def test_cors_preflight_uses_configured_origins() -> None:
    config = AppConfig.model_validate(
        {
            "app": {"name": "test"},
            "logging": {"colors": False},
            "cors": {"allow_origins": ["http://example.test"]},
        }
    )
    container = create_container(config)
    app = create_app(container)

    with TestClient(app) as client:
        response = client.options(
            "/healthz",
            headers={
                "origin": "http://example.test",
                "access-control-request-method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://example.test"
