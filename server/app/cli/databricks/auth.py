"""Databricks workspace authentication: profile, OAuth M2M and Azure AD."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from databricks.sdk import WorkspaceClient

_ENV_HOST = "DATABRICKS_HOST"
_ENV_PROFILE = "DATABRICKS_CONFIG_PROFILE"
_ENV_CLIENT_ID = "DATABRICKS_CLIENT_ID"
_ENV_CLIENT_SECRET = "DATABRICKS_CLIENT_SECRET"
_ENV_AZURE_CLIENT_ID = "AZURE_CLIENT_ID"
_ENV_AZURE_CLIENT_SECRET = "AZURE_CLIENT_SECRET"
_ENV_AZURE_TENANT_ID = "AZURE_TENANT_ID"

_PROFILE_METHOD = "--profile"
_SERVICE_PRINCIPAL_METHOD = "--client-id/--client-secret"
_AZURE_METHOD = "--azure-client-id/--azure-client-secret"

_OAuth_M2M = "oauth-m2m"
_AZURE_CLIENT_SECRET = "azure-client-secret"


class DatabricksAuthError(RuntimeError):
    """Raised when the requested authentication method cannot be configured."""


def _env(name: str) -> str | None:
    """Return a non-empty environment variable value."""
    return os.environ.get(name) or None


@dataclass(frozen=True, slots=True)
class DatabricksAuthConfig:
    """Authentication inputs, from CLI options or the ambient environment."""

    host: str | None = None
    profile: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    azure_client_id: str | None = None
    azure_client_secret: str | None = None
    azure_tenant_id: str | None = None

    def explicit_methods(self) -> list[str]:
        """Return the authentication methods the caller named explicitly."""
        return [
            name
            for name, given in (
                (_PROFILE_METHOD, self.profile is not None),
                (
                    _SERVICE_PRINCIPAL_METHOD,
                    self.client_id is not None or self.client_secret is not None,
                ),
                (
                    _AZURE_METHOD,
                    self.azure_client_id is not None
                    or self.azure_client_secret is not None
                    or self.azure_tenant_id is not None,
                ),
            )
            if given
        ]


class DatabricksClientFactory:
    """Build a ``WorkspaceClient`` for exactly one authentication method.

    Explicit options win over the environment, so a repository ``.env`` can hold
    one method while a flag selects another. The chosen method pins the SDK
    ``auth_type``, which also stops ambient credentials from configuring a
    second, conflicting authorization method.
    """

    def __init__(self, create_client: Callable[..., WorkspaceClient]) -> None:
        """Store the factory used to build the SDK client."""
        self._create_client = create_client

    def create(self, config: DatabricksAuthConfig) -> WorkspaceClient:
        """Resolve the authentication method and construct the client."""
        options = self._client_options(config)
        try:
            return self._create_client(**options)
        except ValueError as error:
            # The SDK rejects a Config with two authorization methods.
            raise DatabricksAuthError(str(error)) from error

    def _client_options(self, config: DatabricksAuthConfig) -> dict[str, Any]:
        """Return the SDK keyword arguments for one resolved method."""
        explicit = config.explicit_methods()
        if len(explicit) > 1:
            raise DatabricksAuthError(
                "use only one authentication method, got " + ", ".join(explicit)
            )

        host = config.host or _env(_ENV_HOST)
        if not host:
            raise DatabricksAuthError("--host is required (or set DATABRICKS_HOST)")

        profile = config.profile or _env(_ENV_PROFILE)
        client_id = config.client_id or _env(_ENV_CLIENT_ID)
        client_secret = config.client_secret or _env(_ENV_CLIENT_SECRET)
        azure_client_id = config.azure_client_id or _env(_ENV_AZURE_CLIENT_ID)
        azure_client_secret = config.azure_client_secret or _env(
            _ENV_AZURE_CLIENT_SECRET
        )
        azure_tenant_id = config.azure_tenant_id or _env(_ENV_AZURE_TENANT_ID)

        method = self._select_method(
            explicit,
            profile=profile,
            service_principal=bool(client_id and client_secret),
            azure=bool(azure_client_id and azure_client_secret),
        )

        options: dict[str, Any] = {"host": host}
        if method == _AZURE_METHOD:
            if not (azure_client_id and azure_client_secret):
                raise DatabricksAuthError(
                    f"{_AZURE_METHOD} (or {_ENV_AZURE_CLIENT_ID}/"
                    f"{_ENV_AZURE_CLIENT_SECRET}) must be provided together"
                )
            options["azure_client_id"] = azure_client_id
            options["azure_client_secret"] = azure_client_secret
            options["auth_type"] = _AZURE_CLIENT_SECRET
            if azure_tenant_id:
                options["azure_tenant_id"] = azure_tenant_id
        elif method == _SERVICE_PRINCIPAL_METHOD:
            if not (client_id and client_secret):
                raise DatabricksAuthError(
                    f"{_SERVICE_PRINCIPAL_METHOD} (or {_ENV_CLIENT_ID}/"
                    f"{_ENV_CLIENT_SECRET}) must be provided together"
                )
            options["client_id"] = client_id
            options["client_secret"] = client_secret
            options["auth_type"] = _OAuth_M2M
        elif method == _PROFILE_METHOD:
            options["profile"] = profile
        return options

    @staticmethod
    def _select_method(
        explicit: list[str],
        *,
        profile: str | None,
        service_principal: bool,
        azure: bool,
    ) -> str | None:
        """Pick one authentication method, letting explicit options win.

        With no explicit option the environment decides, preferring a profile,
        then Databricks OAuth service-principal credentials, then Azure AD
        credentials; ``None`` leaves the choice to the SDK's own detection.
        """
        if explicit:
            return explicit[0]
        if profile:
            return _PROFILE_METHOD
        if service_principal:
            return _SERVICE_PRINCIPAL_METHOD
        if azure:
            return _AZURE_METHOD
        return None
