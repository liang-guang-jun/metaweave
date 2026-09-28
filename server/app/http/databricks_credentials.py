"""Request scoped Databricks Apps credentials for downstream clients."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token

_access_token: ContextVar[str | None] = ContextVar(
    "databricks_apps_access_token", default=None
)


def request_credential() -> str | None:
    """Return the forwarded token in the current HTTP request, if present."""
    return _access_token.get()


def set_request_credential(value: str | None) -> Token[str | None]:
    """Bind one forwarded credential to the current request context."""
    return _access_token.set(value)


def reset_request_credential(token: Token[str | None]) -> None:
    """Restore the previous request context after a response."""
    _access_token.reset(token)


class DatabricksWorkspaceCredentialAdapter[TClient]:
    """Choose a user credential when forwarded, else the default app client."""

    def __init__(
        self,
        default_client: Callable[[], TClient],
        user_client: Callable[[str], TClient],
    ) -> None:
        """Store factories without retaining any request token."""
        self._default_client = default_client
        self._user_client = user_client

    def client(self) -> TClient:
        """Build a user client for this request or use ambient app auth."""
        token = request_credential()
        return self._user_client(token) if token else self._default_client()
