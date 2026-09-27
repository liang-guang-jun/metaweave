from __future__ import annotations

from fastapi.testclient import TestClient

from server.app.bootstrap import AppConfig, create_container
from server.app.http import create_app


def _client(**overrides: object) -> TestClient:
    config = AppConfig.model_validate({"logging": {"colors": False}, **overrides})
    return TestClient(create_app(create_container(config)))


def test_healthz_reports_registration_availability() -> None:
    with _client() as client:
        enabled = client.get("/healthz")
    with _client(register={"enabled": False}) as client:
        disabled = client.get("/healthz")

    assert enabled.json()["register_enabled"] is True
    assert disabled.json()["register_enabled"] is False


def test_healthz_mirrors_the_email_verification_setting() -> None:
    with _client() as client:
        default = client.get("/healthz")
    with _client(register={"email": {"skip_verify": False}}) as client:
        verifying = client.get("/healthz")

    assert default.json()["register_skip_verify"] is True
    assert verifying.json()["register_skip_verify"] is False


def test_healthz_mirrors_the_configured_password_policy() -> None:
    with _client(
        password_policy={
            "min_length": 20,
            "require_upper": False,
            "require_digit": True,
            "require_symbol": False,
        }
    ) as client:
        response = client.get("/healthz")

    assert response.json()["password_policy"] == {
        "min_length": 20,
        "require_upper": False,
        "require_digit": True,
        "require_symbol": False,
    }


def test_register_endpoint_is_forbidden_when_registration_is_disabled() -> None:
    with _client(register={"enabled": False}) as client:
        response = client.post(
            "/iam/users",
            json={"email": "user@example.test", "password": "Password1!"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "self-service registration is disabled"}
