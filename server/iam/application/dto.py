"""IAM application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..domain.services import AccessDecision
from ..domain.value_objects import *


@dataclass(frozen=True, slots=True)
class MembershipDTO:
    membership_id: MembershipId
    tenant_id: TenantId
    user_id: UserId
    active: bool
    is_admin: bool
    email: str | None = None
    membership_type: TenantMembershipType = TenantMembershipType.MEMBER


@dataclass(frozen=True, slots=True)
class GroupMembershipDTO:
    membership_id: GroupMembershipId
    group_id: GroupId
    member_id: UserId | GroupId
    member_type: GroupMemberType
    active: bool
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class TenantDTO:
    tenant_id: TenantId
    name: str


@dataclass(frozen=True, slots=True)
class UserDTO:
    user_id: UserId
    email: str
    active: bool


@dataclass(frozen=True, slots=True)
class GroupDTO:
    group_id: GroupId
    tenant_id: TenantId
    name: str


@dataclass(frozen=True, slots=True)
class Principal:
    subject_id: UserId
    subject_type: str
    tenant_id: TenantId
    membership_id: MembershipId
    session_id: SessionId


@dataclass(frozen=True, slots=True)
class TokenClaims:
    subject: UserId
    tenant_id: TenantId | None
    membership_id: MembershipId | None
    session_id: SessionId | None
    auth_method: str
    issuer: str
    audience: str
    expires_at: datetime

    def as_dict(self) -> dict[str, str | int]:
        values: dict[str, str | int] = {
            "sub": str(self.subject),
            "auth_method": self.auth_method,
            "iss": self.issuer,
            "aud": self.audience,
            "exp": int(self.expires_at.timestamp()),
        }
        if self.tenant_id is not None:
            values["tenant_id"] = str(self.tenant_id)
        if self.membership_id is not None:
            values["membership_id"] = str(self.membership_id)
        if self.session_id is not None:
            values["session_id"] = str(self.session_id)
        return values


@dataclass(frozen=True, slots=True)
class IssuedToken:
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class LoginResult:
    user_id: UserId
    memberships: tuple[MembershipDTO, ...]


@dataclass(frozen=True, slots=True)
class BatchAccessDecision:
    decisions: tuple[AccessDecision, ...]
