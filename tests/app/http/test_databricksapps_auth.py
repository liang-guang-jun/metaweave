"""Databricks Apps header authentication and transient credentials."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select, update

from server.app.bootstrap import AppConfig, create_container
from server.app.cli.db import apply_migrations
from server.app.http import create_app
from server.app.http.databricks_credentials import (
    DatabricksWorkspaceCredentialAdapter,
    request_credential,
    reset_request_credential,
    set_request_credential,
)
from server.iam.infrastructure.persistence.sqlalchemy.models import (
    ExternalSSOIdentityRecord,
    PrincipalRecord,
    SSOProviderRecord,
    UserRecord,
)


def test_provider_config_defaults_and_header_validation() -> None:
    providers = AppConfig().iam.identity.providers
    assert providers.local.enabled and providers.databricksapps.enabled
    assert providers.databricksapps.ignore_status is False
    for invalid in ("", "has space", "X-Bad\nHeader"):
        with pytest.raises(ValidationError):
            AppConfig.model_validate(
                {
                    "iam": {
                        "identity": {
                            "providers": {
                                "databricksapps": {"headers": {"email": invalid}}
                            }
                        }
                    }
                }
            )


def test_request_credential_adapter_uses_user_token_only_within_request() -> None:
    adapter = DatabricksWorkspaceCredentialAdapter(
        lambda: "app", lambda token: f"user:{token}"
    )
    assert adapter.client() == "app"
    marker = set_request_credential("secret-token")
    try:
        assert request_credential() == "secret-token"
        assert adapter.client() == "user:secret-token"
    finally:
        reset_request_credential(marker)
    assert adapter.client() == "app"


@pytest.fixture
def app_client() -> Iterator[tuple[TestClient, object]]:
    config = AppConfig.model_validate(
        {
            "logging": {"colors": False},
            "database": {
                "provider": "sqlite",
                "driver": "aiosqlite",
                "database": ":memory:",
                "auth": {"type": "none"},
            },
            "iam": {"token": {"secret": "test-secret-long-enough-for-signing"}},
        }
    )
    container = create_container(config)
    apply_migrations(container.engine())
    with TestClient(create_app(container)) as client:
        yield client, container


def test_missing_email_returns_401(app_client: tuple[TestClient, object]) -> None:
    client, _ = app_client
    assert client.post("/iam/auth/databricksapps").status_code == 401


def test_login_creates_verified_user_and_is_idempotent(
    app_client: tuple[TestClient, object],
) -> None:
    client, container = app_client
    for _ in range(2):
        response = client.post(
            "/iam/auth/databricksapps",
            headers={"X-Forwarded-Email": "USER@example.test"},
        )
        assert response.status_code == 200, response.text
        token = response.json()["access_token"]
        claims = jwt.decode(
            token,
            container.config().iam.token.secret,
            algorithms=["HS256"],
            audience="business-api",
            issuer="iam",
        )
        assert claims["auth_method"] == "DATABRICKS_APPS"
        assert "USER@example.test" not in str(claims)
        assert (
            client.get("/iam/me", headers={"X-Bearer-Token": token}).status_code == 200
        )
    assert request_credential() is None

    async def counts():
        async with container.session_factory()() as session:
            providers = (await session.scalars(select(SSOProviderRecord))).all()
            identities = (
                await session.scalars(select(ExternalSSOIdentityRecord))
            ).all()
            users = (await session.scalars(select(UserRecord))).all()
            return providers, identities, users

    providers, identities, users = asyncio.run(counts())
    assert len(providers) == len(identities) == len(users) == 1
    assert providers[0].is_global is True
    assert identities[0].user_id == users[0].id
    assert users[0].verified is True and users[0].active is True


def test_existing_user_status_and_ignore_verified(
    app_client: tuple[TestClient, object],
) -> None:
    client, container = app_client
    response = client.post(
        "/iam/users",
        json={"email": "existing@example.test", "password": "Password12345!"},
    )
    assert response.status_code == 201, response.text

    async def change_user(*, verified: bool, active: bool):
        async with container.session_factory()() as session:
            async with session.begin():
                await session.execute(
                    update(UserRecord)
                    .where(UserRecord.email == "existing@example.test")
                    .values(verified=verified)
                )
                user_id = await session.scalar(
                    select(UserRecord.id).where(
                        UserRecord.email == "existing@example.test"
                    )
                )
                await session.execute(
                    update(PrincipalRecord)
                    .where(PrincipalRecord.id == user_id)
                    .values(active=active)
                )

    asyncio.run(change_user(verified=False, active=True))
    headers = {"X-Forwarded-Email": "existing@example.test"}
    assert client.post("/iam/auth/databricksapps", headers=headers).status_code == 401
    assert client.post("/iam/auth/databricksapps", headers=headers).status_code == 401

    config = container.config()
    relaxed = config.model_copy(
        update={
            "iam": config.iam.model_copy(
                update={
                    "identity": config.iam.identity.model_copy(
                        update={
                            "providers": config.iam.identity.providers.model_copy(
                                update={
                                    "databricksapps": config.iam.identity.providers.databricksapps.model_copy(
                                        update={"ignore_status": True}
                                    )
                                }
                            )
                        }
                    )
                }
            )
        }
    )
    container.config.override(relaxed)
    assert client.post("/iam/auth/databricksapps", headers=headers).status_code == 200
    asyncio.run(change_user(verified=False, active=False))
    assert client.post("/iam/auth/databricksapps", headers=headers).status_code == 401


def test_provider_switches_and_custom_headers(
    app_client: tuple[TestClient, object],
) -> None:
    client, container = app_client
    config = container.config()
    providers = config.iam.identity.providers
    configured = providers.model_copy(
        update={
            "local": providers.local.model_copy(update={"enabled": False}),
            "databricksapps": providers.databricksapps.model_copy(
                update={
                    "headers": providers.databricksapps.headers.model_copy(
                        update={"email": "X-User-Mail", "access_token": "X-User-Token"}
                    )
                }
            ),
        }
    )
    container.config.override(
        config.model_copy(
            update={
                "iam": config.iam.model_copy(
                    update={
                        "identity": config.iam.identity.model_copy(
                            update={"providers": configured}
                        )
                    }
                )
            }
        )
    )
    health = client.get("/healthz").json()
    assert health["identity_providers"]["local"]["enabled"] is False
    assert (
        health["identity_providers"]["databricksapps"]["headers"]["email"]
        == "X-User-Mail"
    )
    assert (
        client.post(
            "/iam/auth/token", data={"username": "x", "password": "y"}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/iam/auth/databricksapps", headers={"X-Forwarded-Email": "x@example.test"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/iam/auth/databricksapps", headers={"X-User-Mail": "x@example.test"}
        ).status_code
        == 200
    )
