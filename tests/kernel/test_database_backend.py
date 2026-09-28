from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import cast

import pytest
from databricks.sdk import WorkspaceClient
from pydantic import ValidationError

from server.app.bootstrap.config import AppConfig
from server.kernel.infrastructure.persistence.sqlalchemy.backend import (
    DatabaseConfigurationError,
    DatabricksLakebaseCredentialProvider,
    create_database_backend,
)


def _lakebase_config() -> AppConfig:
    return AppConfig.model_validate(
        {
            "database": {
                "provider": "databricks_lakebase",
                "driver": "asyncpg",
                "auth": {"type": "databricks_app"},
            }
        }
    )


def _environment() -> dict[str, str]:
    return {
        "PGHOST": "lakebase.example.test",
        "PGPORT": "5432",
        "PGDATABASE": "metaweave",
        "PGUSER": "app-service-principal",
        "PGSSLMODE": "require",
        "LAKEBASE_ENDPOINT": "projects/p/branches/b/endpoints/e",
    }


def test_postgresql_backend_uses_asyncpg_and_static_password() -> None:
    config = AppConfig.model_validate(
        {
            "database": {
                "provider": "postgresql",
                "driver": "asyncpg",
                "host": "localhost",
                "port": 5432,
                "database": "metaweave",
                "username": "metaweave",
                "password": "development-only",
                "sslmode": "prefer",
                "auth": {"type": "password"},
            }
        }
    )
    backend = create_database_backend(config.database)

    assert str(backend.url()) == "postgresql+asyncpg://metaweave@localhost:5432/metaweave?sslmode=prefer"


def test_lakebase_backend_reads_databricks_runtime_environment() -> None:
    workspace = object()
    backend = create_database_backend(
        _lakebase_config().database,
        workspace=cast(WorkspaceClient, workspace),
        environment=_environment(),
    )

    assert str(backend.url()) == "postgresql+asyncpg://app-service-principal@lakebase.example.test:5432/metaweave?sslmode=require"
    assert "token" not in str(backend.url())


@pytest.mark.parametrize("name", sorted(_environment()))
def test_lakebase_requires_each_runtime_value(name: str) -> None:
    environment = _environment()
    environment.pop(name)

    with pytest.raises(DatabaseConfigurationError, match=name):
        create_database_backend(
            _lakebase_config().database,
            workspace=cast(WorkspaceClient, object()),
            environment=environment,
        )


def test_lakebase_credential_provider_generates_a_token_without_storing_it() -> None:
    calls: list[str] = []

    class Postgres:
        def generate_database_credential(self, *, endpoint: str) -> object:
            calls.append(endpoint)
            return SimpleNamespace(token="temporary-token")

    workspace = SimpleNamespace(postgres=Postgres())
    provider = DatabricksLakebaseCredentialProvider(
        cast(WorkspaceClient, workspace), "endpoint"
    )

    assert asyncio.run(provider.password()) == "temporary-token"
    assert calls == ["endpoint"]
    assert "temporary-token" not in repr(provider)


def test_invalid_provider_auth_combinations_fail_validation() -> None:
    with pytest.raises(ValidationError, match="requires driver"):
        AppConfig.model_validate(
            {"database": {"provider": "sqlite", "auth": {"type": "password"}}}
        )
