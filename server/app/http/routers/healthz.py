"""Service liveness endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...bootstrap.container import Container
from ..dependencies import get_container

router = APIRouter(tags=["system"])


class PasswordPolicyResponse(BaseModel):
    """Password rules the register endpoint enforces, mirrored to clients."""

    min_length: int
    require_upper: bool
    require_digit: bool
    require_symbol: bool


class HealthzResponse(BaseModel):
    """Liveness response returned by the health probe."""

    status: str
    register_enabled: bool
    # Mirrors `register.email.skip_verify`: accounts created through the register
    # endpoint are already verified, so clients must not demand verification.
    register_skip_verify: bool
    # Header the API expects the access token in, so clients can follow the
    # configured name instead of hardcoding one.
    token_header: str
    password_policy: PasswordPolicyResponse


@router.get("/healthz", response_model=HealthzResponse)
async def healthz(
    container: Annotated[Container, Depends(get_container)],
) -> HealthzResponse:
    """Report liveness, registration availability, and password rules."""
    config = container.config()
    policy = config.password_policy
    return HealthzResponse(
        status="ok",
        register_enabled=config.registration.enabled,
        register_skip_verify=config.registration.email.skip_verify,
        token_header=config.token.header,
        password_policy=PasswordPolicyResponse(
            min_length=policy.min_length,
            require_upper=policy.require_upper,
            require_digit=policy.require_digit,
            require_symbol=policy.require_symbol,
        ),
    )
