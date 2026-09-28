"""SSO and workload identity routes with their schemas."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ...application.messages import (
    AddSSOProviderMembership,
    ConfigureSSOProvider,
    CreateServicePrincipal,
    DisablePrincipal,
    IssueApiKey,
    RestorePrincipal,
)
from ...domain.value_objects import (
    SSOProviderId,
    ServicePrincipalId,
    Subject,
    SubjectType,
    TenantId,
)
from ....app.http.dependencies import (
    AuthenticatedPrincipal,
    get_current_principal,
    get_message_bus,
)
from ....kernel.application.messaging.bus import MessageBus

router = APIRouter(prefix="/tenants/{tenant_id}/identities", tags=["iam.identities"])
provider_router = APIRouter(prefix="/sso/providers", tags=["iam.identities"])


class SSOProviderRequest(BaseModel):
    issuer: str
    client_id: str
    client_secret: str
    is_global: bool = False


class ServicePrincipalRequest(BaseModel):
    name: str


@provider_router.post("", status_code=status.HTTP_201_CREATED)
async def configure_sso(
    request: SSOProviderRequest,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> dict[str, UUID]:
    """Create a provider definition; tenant bindings use the membership route."""
    if request.issuer == "databricksapps":
        raise HTTPException(status_code=400, detail="databricksapps issuer is reserved")
    provider_id = await bus.send(
        ConfigureSSOProvider(
            request.issuer,
            request.client_id,
            request.client_secret,
            request.is_global,
        )
    )
    return {"provider_id": provider_id.value}


@router.post("/sso/{provider_id}/membership", status_code=status.HTTP_201_CREATED)
async def add_sso_membership(
    tenant_id: UUID,
    provider_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> dict[str, UUID]:
    await bus.send(
        AddSSOProviderMembership(SSOProviderId(provider_id), TenantId(tenant_id))
    )
    return {"provider_id": provider_id, "tenant_id": tenant_id}


@router.post("/service-principals", status_code=status.HTTP_201_CREATED)
async def create_service_principal(
    tenant_id: UUID,
    request: ServicePrincipalRequest,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> dict[str, UUID]:
    """Create a tenant workload identity."""
    principal_id = await bus.send(
        CreateServicePrincipal(TenantId(tenant_id), request.name)
    )
    return {"principal_id": principal_id.value}


@router.post(
    "/service-principals/{principal_id}/api-keys", status_code=status.HTTP_201_CREATED
)
async def issue_api_key(
    principal_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> dict[str, str]:
    """Issue an API key; the secret is returned only once."""
    key_id, secret = await bus.send(IssueApiKey(ServicePrincipalId(principal_id)))
    return {"api_key_id": str(key_id), "secret": secret}


@router.post(
    "/service-principals/{principal_id}/disable", status_code=status.HTTP_204_NO_CONTENT
)
async def disable_service_principal(
    principal_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> None:
    """Disable a tenant workload identity; tenant-admin authorization is handler-owned."""
    await bus.send(
        DisablePrincipal(
            Subject(ServicePrincipalId(principal_id), SubjectType.SERVICE_PRINCIPAL)
        )
    )


@router.post(
    "/service-principals/{principal_id}/restore", status_code=status.HTTP_204_NO_CONTENT
)
async def restore_service_principal(
    principal_id: UUID,
    bus: Annotated[MessageBus, Depends(get_message_bus)],
    _: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
) -> None:
    """Restore a disabled tenant workload identity; authorization remains handler-owned."""
    await bus.send(
        RestorePrincipal(
            Subject(ServicePrincipalId(principal_id), SubjectType.SERVICE_PRINCIPAL)
        )
    )
