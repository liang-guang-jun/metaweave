"""IAM commands and queries."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ...kernel.application.messaging.message import Command, Query
from ...kernel.application.common.page import Page, PageRequest
from ..domain.entities import AccessControlList, Session
from ..domain.services import AccessDecision
from ..domain.value_objects import *
from .dto import *


@dataclass(frozen=True, slots=True)
class RegisterUser(Command[UserId]):
    email: str
    password: str


@dataclass(frozen=True, slots=True)
class BootstrapSystemAdmin(Command[UserId]):
    """Create the first verified user and grant instance administration."""

    email: str
    password: str


@dataclass(frozen=True, slots=True)
class VerifyUser(Command[None]):
    user_id: UserId


@dataclass(frozen=True, slots=True)
class ChangePassword(Command[None]):
    user_id: UserId
    password: str


@dataclass(frozen=True, slots=True)
class DisablePrincipal(Command[None]):
    """Disable a human or workload principal without deleting its identity."""

    subject: Subject


@dataclass(frozen=True, slots=True)
class RestorePrincipal(Command[None]):
    """Restore a previously disabled human or workload principal."""

    subject: Subject


@dataclass(frozen=True, slots=True)
class CreateTenant(Command[TenantId]):
    name: str
    owner_user_id: UserId | None = None


@dataclass(frozen=True, slots=True)
class GrantSystemAdmin(Command[None]):
    subject: Subject


@dataclass(frozen=True, slots=True)
class RevokeSystemAdmin(Command[None]):
    subject: Subject


@dataclass(frozen=True, slots=True)
class InviteMember(Command[MembershipId]):
    tenant_id: TenantId
    user_id: UserId
    is_admin: bool = False
    membership_type: TenantMembershipType | None = None


@dataclass(frozen=True, slots=True)
class AcceptInvitation(Command[None]):
    membership_id: MembershipId


@dataclass(frozen=True, slots=True)
class RemoveMember(Command[None]):
    membership_id: MembershipId


@dataclass(frozen=True, slots=True)
class DisableMembership(Command[None]):
    membership_id: MembershipId


@dataclass(frozen=True, slots=True)
class RestoreMembership(Command[None]):
    membership_id: MembershipId


@dataclass(frozen=True, slots=True)
class PromoteMember(Command[None]):
    membership_id: MembershipId


@dataclass(frozen=True, slots=True)
class DemoteAdmin(Command[None]):
    membership_id: MembershipId


@dataclass(frozen=True, slots=True)
class RegisterAcl(Command[AclId]):
    scope: AclScope


@dataclass(frozen=True, slots=True)
class GrantAccess(Command[None]):
    scope: AclScope
    subject: Subject
    action: Action
    effect: Effect = Effect.ALLOW


@dataclass(frozen=True, slots=True)
class RevokeAccess(Command[None]):
    scope: AclScope
    subject: Subject
    action: Action


@dataclass(frozen=True, slots=True)
class DeleteAcl(Command[None]):
    scope: AclScope


@dataclass(frozen=True, slots=True)
class CreateGroup(Command[GroupId]):
    tenant_id: TenantId
    name: str


@dataclass(frozen=True, slots=True)
class AddGroupMember(Command[None]):
    group_id: GroupId
    member_id: UserId | GroupId
    member_type: GroupMemberType | None = None


@dataclass(frozen=True, slots=True)
class RemoveGroupMember(Command[None]):
    membership_id: GroupMembershipId
    group_id: GroupId | None = None


@dataclass(frozen=True, slots=True)
class RestoreGroupMember(Command[None]):
    membership_id: GroupMembershipId
    group_id: GroupId | None = None


@dataclass(frozen=True, slots=True)
class ConfigureSSOProvider(Command[SSOProviderId]):
    tenant_id: TenantId
    issuer: str
    client_id: str
    client_secret: str


@dataclass(frozen=True, slots=True)
class LinkExternalSSOIdentity(Command[ExternalSSOIdentityId]):
    user_id: UserId
    provider_id: SSOProviderId
    external_subject: str


@dataclass(frozen=True, slots=True)
class CreateServicePrincipal(Command[ServicePrincipalId]):
    tenant_id: TenantId
    name: str


@dataclass(frozen=True, slots=True)
class IssueApiKey(Command[tuple[ApiKeyId, str]]):
    principal_id: ServicePrincipalId


@dataclass(frozen=True, slots=True)
class RevokeApiKey(Command[None]):
    api_key_id: ApiKeyId


@dataclass(frozen=True, slots=True)
class LoginWithPassword(Command[LoginResult]):
    email: str
    password: str


@dataclass(frozen=True, slots=True)
class IssuePreAuthToken(Command[IssuedToken]):
    """Issue an identity-only token before a tenant has been selected."""

    user_id: UserId
    auth_method: str = "PASSWORD"


@dataclass(frozen=True, slots=True)
class LoginWithOidc(Command[LoginResult]):
    token: str


@dataclass(frozen=True, slots=True)
class SelectTenantAndIssueTokens(Command[IssuedToken]):
    user_id: UserId
    tenant_id: TenantId
    auth_method: str = "PASSWORD"


@dataclass(frozen=True, slots=True)
class RevokeSession(Command[None]):
    session_id: SessionId


@dataclass(frozen=True, slots=True)
class ListUserMemberships(Query[tuple[MembershipDTO, ...]]):
    user_id: UserId


@dataclass(frozen=True, slots=True)
class ListTenantMemberships(Query[tuple[MembershipDTO, ...]]):
    tenant_id: TenantId


@dataclass(frozen=True, slots=True)
class SearchTenantMemberships(Query[Page[MembershipDTO]]):
    tenant_id: TenantId
    keyword: str = ""
    page: PageRequest = field(default_factory=PageRequest)


@dataclass(frozen=True, slots=True)
class SearchGroupMemberships(Query[Page[GroupMembershipDTO]]):
    group_id: GroupId
    keyword: str = ""
    page: PageRequest = field(default_factory=PageRequest)


@dataclass(frozen=True, slots=True)
class GetCurrentUser(Query[UserDTO | None]):
    """Resolve the authenticated user's own directory entry."""

    user_id: UserId


@dataclass(frozen=True, slots=True)
class SearchUsers(Query[Page[UserDTO]]):
    keyword: str = ""
    page: PageRequest = field(default_factory=PageRequest)


@dataclass(frozen=True, slots=True)
class ListAvailableTenants(Query[Page[TenantDTO]]):
    user_id: UserId
    keyword: str = ""
    page: PageRequest = field(default_factory=PageRequest)


@dataclass(frozen=True, slots=True)
class SearchGroups(Query[Page[GroupDTO]]):
    tenant_id: TenantId
    keyword: str = ""
    page: PageRequest = field(default_factory=PageRequest)


@dataclass(frozen=True, slots=True)
class CheckAccess(Query[AccessDecision]):
    tenant_id: TenantId
    user_id: UserId
    resource_type: str
    resource_id: str
    action: Action


@dataclass(frozen=True, slots=True)
class BatchCheckAccess(Query[BatchAccessDecision]):
    tenant_id: TenantId
    user_id: UserId
    requests: tuple[tuple[str, str, Action], ...]


@dataclass(frozen=True, slots=True)
class GetSession(Query[Session | None]):
    session_id: SessionId


@dataclass(frozen=True, slots=True)
class IsPrincipalActive(Query[bool]):
    """Read the lifecycle state of an authenticated polymorphic principal."""

    subject: Subject


@dataclass(frozen=True, slots=True)
class GetAcl(Query[AccessControlList | None]):
    scope: AclScope
