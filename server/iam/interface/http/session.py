"""OAuth2 authentication and session routes with their schemas."""

from __future__ import annotations

import time
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from ...application.dto import IssuedToken
from ...application.messages import (
    IssuePreAuthToken,
    ListAvailableTenants,
    LoginWithPassword,
    SelectTenantAndIssueTokens,
)
from ...domain.value_objects import TenantId, UserId
from ....app.http.dependencies import (
    AuthenticatedPrincipal,
    get_authenticated_identity,
    get_message_bus,
)
from ....kernel.application.messaging.bus import MessageBus
from ....kernel.application.common.page import PageRequest

router = APIRouter(prefix="/auth", tags=["iam.auth"])


class TokenResponse(BaseModel):
    """OAuth2-compatible bearer token response."""

    access_token: str
    token_type: str
    expires_in: int | None = None


class TenantOption(BaseModel):
    tenant_id: UUID
    name: str


class TenantOptionPage(BaseModel):
    items: list[TenantOption]
    total: int
    page: int
    size: int
    pages: int
    has_next: bool


@router.get("/tenants", response_model=TenantOptionPage)
async def list_available_tenants(
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_authenticated_identity)],
    keyword: str = Query(default="", max_length=255),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> TenantOptionPage:
    """List active tenant memberships available for tenant switching."""
    result = await bus.ask(
        ListAvailableTenants(
            UserId(principal.user_id), keyword, PageRequest(page, size)
        )
    )
    if result is None:
        result = TenantOptionPage(items=[], total=0, page=page, size=size, pages=0, has_next=False)
        return result
    return TenantOptionPage(
        items=[TenantOption(tenant_id=item.tenant_id.value, name=item.name) for item in result.items],
        total=result.total,
        page=result.page,
        size=result.size,
        pages=result.pages,
        has_next=result.has_next,
    )


@router.post("/token", response_model=TokenResponse)
async def issue_token(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    bus: Annotated[MessageBus, Depends(get_message_bus)],
) -> TokenResponse:
    """Authenticate OAuth2 form credentials and issue an identity-only token."""
    login = await bus.send(LoginWithPassword(form.username, form.password))
    result: IssuedToken = await bus.send(IssuePreAuthToken(login.user_id))
    expires_in = (
        max(0, int(result.expires_at.timestamp() - time.time()))
        if result.expires_at
        else None
    )
    return TokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        expires_in=expires_in,
    )


@router.post("/tenant-token", response_model=TokenResponse)
async def issue_tenant_token(
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    selected_tenant_id: Annotated[UUID, Header(alias="X-Tenant-ID")],
    principal: Annotated[AuthenticatedPrincipal, Depends(get_authenticated_identity)],
) -> TokenResponse:
    """Issue a tenant-scoped token for a tenant the authenticated user can access."""
    result: IssuedToken = await bus.send(
        SelectTenantAndIssueTokens(
            UserId(principal.user_id), TenantId(selected_tenant_id)
        )
    )
    expires_in = (
        max(0, int(result.expires_at.timestamp() - time.time()))
        if result.expires_at
        else None
    )
    return TokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
        expires_in=expires_in,
    )


@router.post("/password")
async def login_password(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    bus: Annotated[MessageBus, Depends(get_message_bus)],
) -> dict[str, object]:
    """Authenticate and return memberships for tenant selection."""
    result = await bus.send(LoginWithPassword(form.username, form.password))
    return {
        "user_id": str(result.user_id),
        "memberships": [
            {
                "membership_id": str(item.membership_id),
                "tenant_id": str(item.tenant_id),
                "active": item.active,
                "is_admin": item.is_admin,
                "membership_type": item.membership_type.value,
            }
            for item in result.memberships
        ],
    }
