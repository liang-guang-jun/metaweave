"""Internal IAM domain events."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ...kernel.domain.event import DomainEvent
from .value_objects import (
    AccessControlEntry,
    AclId,
    AclScope,
    ApiKeyId,
    ExternalSSOIdentityId,
    GroupId,
    GroupMemberType,
    GroupMembershipId,
    MembershipId,
    SessionId,
    ServicePrincipalId,
    SSOProviderId,
    TenantId,
    UserId,
    SubjectType,
)


@dataclass(frozen=True, slots=True)
class UserRegistered(DomainEvent):
    user_id: UserId
    email: str


@dataclass(frozen=True, slots=True)
class UserVerified(DomainEvent):
    user_id: UserId


@dataclass(frozen=True, slots=True)
class PasswordChanged(DomainEvent):
    user_id: UserId


@dataclass(frozen=True, slots=True)
class PrincipalDisabled(DomainEvent):
    """A polymorphic principal can no longer authenticate or act."""

    principal_id: UserId | ServicePrincipalId
    principal_type: SubjectType


@dataclass(frozen=True, slots=True)
class PrincipalRestored(DomainEvent):
    """A disabled polymorphic principal was made active again."""

    principal_id: UserId | ServicePrincipalId
    principal_type: SubjectType


@dataclass(frozen=True, slots=True)
class TenantCreated(DomainEvent):
    tenant_id: TenantId
    name: str


@dataclass(frozen=True, slots=True)
class MembershipInvited(DomainEvent):
    membership_id: MembershipId
    tenant_id: TenantId
    user_id: UserId


@dataclass(frozen=True, slots=True)
class MembershipAccepted(DomainEvent):
    membership_id: MembershipId


@dataclass(frozen=True, slots=True)
class MembershipRemoved(DomainEvent):
    membership_id: MembershipId


@dataclass(frozen=True, slots=True)
class MembershipRestored(DomainEvent):
    membership_id: MembershipId


@dataclass(frozen=True, slots=True)
class MembershipPromoted(DomainEvent):
    membership_id: MembershipId


@dataclass(frozen=True, slots=True)
class MembershipDemoted(DomainEvent):
    membership_id: MembershipId


@dataclass(frozen=True, slots=True)
class AclRegistered(DomainEvent):
    acl_id: AclId
    scope: AclScope


@dataclass(frozen=True, slots=True)
class AccessGranted(DomainEvent):
    acl_id: AclId
    scope: AclScope
    entry: AccessControlEntry


@dataclass(frozen=True, slots=True)
class AccessRevoked(DomainEvent):
    acl_id: AclId
    scope: AclScope
    entry: AccessControlEntry


@dataclass(frozen=True, slots=True)
class AccessRemoved(DomainEvent):
    acl_id: AclId
    scope: AclScope
    entry: AccessControlEntry


@dataclass(frozen=True, slots=True)
class AclDeleted(DomainEvent):
    acl_id: AclId
    scope: AclScope


@dataclass(frozen=True, slots=True)
class SessionCreated(DomainEvent):
    session_id: SessionId
    user_id: UserId
    tenant_id: TenantId


@dataclass(frozen=True, slots=True)
class SessionRevoked(DomainEvent):
    session_id: SessionId


@dataclass(frozen=True, slots=True)
class GroupCreated(DomainEvent):
    group_id: GroupId
    tenant_id: TenantId
    name: str


@dataclass(frozen=True, slots=True)
class GroupMemberAdded(DomainEvent):
    group_id: GroupId
    member_id: UserId | GroupId


@dataclass(frozen=True, slots=True)
class GroupMemberRemoved(DomainEvent):
    group_id: GroupId
    member_id: UserId | GroupId


@dataclass(frozen=True, slots=True)
class GroupMembershipCreated(DomainEvent):
    membership_id: GroupMembershipId
    group_id: GroupId
    member_id: UserId | GroupId
    member_type: GroupMemberType


@dataclass(frozen=True, slots=True)
class GroupMembershipRemoved(DomainEvent):
    membership_id: GroupMembershipId


@dataclass(frozen=True, slots=True)
class GroupMembershipRestored(DomainEvent):
    membership_id: GroupMembershipId


@dataclass(frozen=True, slots=True)
class SSOProviderConfigured(DomainEvent):
    provider_id: SSOProviderId
    tenant_id: TenantId
    issuer: str


@dataclass(frozen=True, slots=True)
class ExternalSSOIdentityLinked(DomainEvent):
    identity_id: ExternalSSOIdentityId
    user_id: UserId
    provider_id: SSOProviderId


@dataclass(frozen=True, slots=True)
class ServicePrincipalCreated(DomainEvent):
    principal_id: ServicePrincipalId
    tenant_id: TenantId
    name: str


@dataclass(frozen=True, slots=True)
class ApiKeyIssued(DomainEvent):
    api_key_id: ApiKeyId
    principal_id: ServicePrincipalId


@dataclass(frozen=True, slots=True)
class ApiKeyRevoked(DomainEvent):
    api_key_id: ApiKeyId
