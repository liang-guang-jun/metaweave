"""ACL decision and mutation routes with their schemas."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from ...application.messages import CheckAccess, GrantAccess, RegisterAcl, RevokeAccess
from ...domain.services import AccessDecision
from ...domain.value_objects import Action, AclScope, Effect, Subject, TenantId, UserId
from ....app.http.dependencies import (
    get_current_principal,
    get_message_bus,
    AuthenticatedPrincipal,
)
from ....kernel.application.messaging.bus import MessageBus

router = APIRouter(prefix="/tenants/{tenant_id}/acl", tags=["iam.acl"])


class RegisterAclRequest(BaseModel):
    resource_type: str
    resource_id: str


class AclEntryRequest(BaseModel):
    user_id: UUID
    action: str
    effect: Effect = Effect.ALLOW


class AccessDecisionResponse(BaseModel):
    permit: bool
    reason: str
    scope: str | None = None


class CheckAccessRequest(BaseModel):
    user_id: UUID
    resource_type: str
    resource_id: str
    action: str


def _decision(value: AccessDecision) -> AccessDecisionResponse:
    return AccessDecisionResponse(
        permit=value.permit,
        reason=value.reason,
        scope=value.scope.resource_id if value.scope else None,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def register_acl(
    tenant_id: UUID,
    request: RegisterAclRequest,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> dict[str, UUID]:
    """Create an ACL scope."""
    acl_id = await bus.send(
        RegisterAcl(
            AclScope(TenantId(tenant_id), request.resource_type, request.resource_id)
        )
    )
    return {"acl_id": acl_id.value}


@router.post("/grant", status_code=status.HTTP_204_NO_CONTENT)
async def grant_access(
    tenant_id: UUID,
    request: AclEntryRequest,
    resource_type: str,
    resource_id: str,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> None:
    """Grant or explicitly deny a user access action."""
    await bus.send(
        GrantAccess(
            AclScope(TenantId(tenant_id), resource_type, resource_id),
            Subject(UserId(request.user_id)),
            Action(request.action),
            request.effect,
        )
    )


@router.post("/check", response_model=AccessDecisionResponse)
async def check_access(
    tenant_id: UUID,
    request: CheckAccessRequest,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> AccessDecisionResponse:
    """Evaluate a user ACL decision against the projection."""
    result = await bus.ask(
        CheckAccess(
            TenantId(tenant_id),
            UserId(request.user_id),
            request.resource_type,
            request.resource_id,
            Action(request.action),
        )
    )
    return _decision(result)
