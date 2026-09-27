from __future__ import annotations

from fastapi.testclient import TestClient

from server.app.bootstrap import AppConfig, create_container
from server.app.http import create_app


def test_api_prefix_normalizes_surrounding_slashes() -> None:
    config = AppConfig.model_validate({"api": {"prefix": "api/v1/"}})

    assert config.api.prefix == "/api/v1"


def test_empty_api_prefix_serves_routes_from_the_root() -> None:
    config = AppConfig.model_validate({"api": {"prefix": "/"}})

    assert config.api.prefix == ""


def test_api_prefix_namespaces_every_router() -> None:
    config = AppConfig.model_validate(
        {"api": {"prefix": "/api/v1"}, "logging": {"colors": False}}
    )
    container = create_container(config)
    app = create_app(container)

    with TestClient(app) as client:
        prefixed = client.get("/api/v1/healthz")
        unprefixed = client.get("/healthz")

    assert prefixed.status_code == 200
    assert prefixed.json()["status"] == "ok"
    assert prefixed.json()["register_enabled"] is True
    assert prefixed.json()["password_policy"]["min_length"] == 12
    assert unprefixed.status_code == 404
