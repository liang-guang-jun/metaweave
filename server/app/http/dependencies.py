"""FastAPI dependencies shared by HTTP routers."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from ...iam.application.messages import IsPrincipalActive
from ...iam.domain.value_objects import Subject, SubjectType, UserId
from ...kernel.application.context import (
    ExecutionContext,
    MessageMetadata,
    current_context_or_none,
    execution_context,
)
from ...kernel.application.messaging.bus import MessageBus
from ..bootstrap.container import Container

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/iam/auth/token", auto_error=False)

_BEARER_PREFIX = "bearer "


@dataclass(frozen=True, slots=True)
class AuthenticatedPrincipal:
    """Validated identity claims extracted from an OAuth2 bearer token."""

    user_id: UUID
    tenant_id: UUID | None
    membership_id: UUID | None
    session_id: UUID | None
    auth_method: str


def get_container(request: Request) -> Container:
    """Return the composition-root container mounted on this FastAPI app."""
    return cast(Container, request.app.state.container)


def get_message_bus(
    container: Container = Depends(get_container),  # noqa: B008
) -> MessageBus:
    """Resolve the single application MessageBus from the mounted container."""
    return container.message_bus()


def _invalid_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _missing_token(header_name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Not authenticated: send the token in {header_name}",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _access_token(
    request: Request,
    bearer: str | None = Depends(oauth2_scheme),
) -> str:
    """Return the access token from the configured header or ``Authorization``.

    ``token.header`` (``X-Bearer-Token`` by default) wins over the standard
    header, whose value a hosting platform proxy may replace with its own token.
    """
    header_name = get_container(request).config().iam.token.header
    token = request.headers.get(header_name) or bearer
    if token and token.lower().startswith(_BEARER_PREFIX):
        token = token[len(_BEARER_PREFIX) :]
    if not token:
        raise _missing_token(header_name)
    return token


def _decode_token(token: str, container: Container) -> AuthenticatedPrincipal:
    config = container.config()
    try:
        payload = jwt.decode(
            token,
            config.iam.token.secret,
            algorithms=["HS256"],
            audience=config.iam.token.audience,
            issuer=config.iam.token.issuer,
        )
        return AuthenticatedPrincipal(
            user_id=UUID(str(payload["sub"])),
            tenant_id=UUID(str(payload["tenant_id"]))
            if payload.get("tenant_id")
            else None,
            membership_id=UUID(str(payload["membership_id"]))
            if payload.get("membership_id")
            else None,
            session_id=UUID(str(payload["session_id"]))
            if payload.get("session_id")
            else None,
            auth_method=str(payload["auth_method"]),
        )
    except (KeyError, TypeError, ValueError, jwt.PyJWTError) as error:
        raise _invalid_token() from error


@contextmanager
def _principal_context(
    principal: AuthenticatedPrincipal,
) -> Generator[None]:
    current = current_context_or_none()
    if current is None:
        metadata = MessageMetadata(
            message_id="http-authenticated",
            correlation_id=None,
            causation_id=None,
            user_id=str(principal.user_id),
            tenant_id=str(principal.tenant_id),
            occurred_at=datetime.now(UTC),
        )
        context = ExecutionContext(metadata)
    else:
        context = current.with_metadata(
            user_id=str(principal.user_id), tenant_id=str(principal.tenant_id)
        )
    with execution_context(context):
        yield


async def get_current_principal(
    request: Request,
    token: str = Depends(_access_token),
    selected_tenant_id: UUID | None = Header(default=None, alias="X-Tenant-ID"),  # noqa: B008
) -> AsyncGenerator[AuthenticatedPrincipal]:
    """Decode bearer identity and bind the explicitly selected tenant context."""
    container = get_container(request)
    principal = _decode_token(token, container)
    if not await container.message_bus().ask(
        IsPrincipalActive(Subject(UserId(principal.user_id), SubjectType.USER))
    ):
        raise _invalid_token()
    principal = AuthenticatedPrincipal(
        principal.user_id,
        selected_tenant_id,
        principal.membership_id,
        principal.session_id,
        principal.auth_method,
    )
    with _principal_context(principal):
        yield principal


async def get_authenticated_identity(
    request: Request,
    token: str = Depends(_access_token),
) -> AuthenticatedPrincipal:
    """Resolve an identity-only or tenant-bound bearer token."""
    container = get_container(request)
    principal = _decode_token(token, container)
    if not await container.message_bus().ask(
        IsPrincipalActive(Subject(UserId(principal.user_id), SubjectType.USER))
    ):
        raise _invalid_token()
    return principal
