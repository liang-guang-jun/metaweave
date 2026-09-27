"""Token channels accepted by the HTTP layer.

A hosting platform proxy owns ``Authorization`` for its own authentication, so the
API also reads the token from the configurable ``token.header`` and prefers it.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from server.app.bootstrap import AppConfig, create_container
from server.app.cli.db import apply_migrations
from server.app.http import create_app

_EMAIL = "member@example.test"
_PASSWORD = "Password1!"
_DEFAULT_HEADER = "X-Bearer-Token"


def _serve(*, header: str | None = None) -> Iterator[TestClient]:
    """Serve the app with a migrated database and one registered user."""
    token_config: dict[str, object] = {
        "secret": "test-secret-long-enough-for-hs256-signing"
    }
    if header is not None:
        token_config["header"] = header
    config = AppConfig.model_validate(
        {
            "logging": {"colors": False},
            "database": {"url": "sqlite+aiosqlite:///:memory:"},
            "password_policy": {"min_length": 8},
            "token": token_config,
        }
    )
    container = create_container(config)
    apply_migrations(container.engine())
    with TestClient(create_app(container)) as test_client:
        registered = test_client.post(
            "/iam/users", json={"email": _EMAIL, "password": _PASSWORD}
        )
        assert registered.status_code == 201, registered.text
        yield test_client


@pytest.fixture
def client() -> Iterator[TestClient]:
    """Serve the app with the default token header."""
    yield from _serve()


def _token(client: TestClient) -> str:
    """Log in and return the issued access token."""
    response = client.post(
        "/iam/auth/token", data={"username": _EMAIL, "password": _PASSWORD}
    )
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token


def test_me_accepts_the_configured_header(client: TestClient) -> None:
    response = client.get("/iam/me", headers={_DEFAULT_HEADER: _token(client)})

    assert response.status_code == 200
    assert response.json()["email"] == _EMAIL


def test_me_accepts_the_authorization_header(client: TestClient) -> None:
    response = client.get(
        "/iam/me", headers={"Authorization": f"Bearer {_token(client)}"}
    )

    assert response.status_code == 200


def test_configured_header_wins_over_a_rewritten_authorization_header(
    client: TestClient,
) -> None:
    headers = {
        _DEFAULT_HEADER: _token(client),
        "Authorization": "Bearer platform-token",
    }

    response = client.get("/iam/me", headers=headers)

    assert response.status_code == 200


def test_tenant_scoped_routes_accept_the_configured_header(
    client: TestClient,
) -> None:
    response = client.get(
        "/iam/auth/tenants", headers={_DEFAULT_HEADER: _token(client)}
    )

    assert response.status_code == 200


def test_missing_credentials_name_the_configured_header(client: TestClient) -> None:
    response = client.get("/iam/me")

    assert response.status_code == 401
    assert response.json() == {
        "detail": f"Not authenticated: send the token in {_DEFAULT_HEADER}"
    }
    assert response.headers["www-authenticate"] == "Bearer"


def test_an_invalid_token_is_reported_as_such(client: TestClient) -> None:
    response = client.get("/iam/me", headers={_DEFAULT_HEADER: "not-a-jwt"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication credentials"}


def test_healthz_reports_the_configured_header(client: TestClient) -> None:
    response = client.get("/healthz")

    assert response.json()["token_header"] == _DEFAULT_HEADER


def test_a_custom_header_name_replaces_the_default() -> None:
    config_header = "X-Custom-Auth"
    for test_client in _serve(header=config_header):
        token = _token(test_client)

        custom = test_client.get("/iam/me", headers={config_header: token})
        default = test_client.get("/iam/me", headers={_DEFAULT_HEADER: token})
        reported = test_client.get("/healthz")

        assert custom.status_code == 200
        assert default.status_code == 401
        assert reported.json()["token_header"] == config_header


def test_a_bearer_prefixed_value_in_the_configured_header_is_accepted(
    client: TestClient,
) -> None:
    headers = {_DEFAULT_HEADER: f"Bearer {_token(client)}"}

    response = client.get("/iam/me", headers=headers)

    assert response.status_code == 200
