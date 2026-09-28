"""IAM application ports."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from ...kernel.application.unit_of_work import UnitOfWork
from ...kernel.application.common.page import Page, PageRequest
from ..domain.entities import (
    AccessControlList,
    ApiKey,
    ExternalSSOIdentity,
    Group,
    GroupMembership,
    Invitation,
    Membership,
    Session,
    ServicePrincipal,
    SSOProvider,
    Tenant,
    User,
)
from ..domain.value_objects import *
from .dto import (
    GroupDTO,
    GroupMembershipDTO,
    IssuedToken,
    MembershipDTO,
    TenantDTO,
    TokenClaims,
    UserDTO,
)


class RepositoryFactory[T](Protocol):
    def __call__(self, uow: UnitOfWork) -> T: ...


class UserRepository(ABC):
    @abstractmethod
    async def get(self, user_id: UserId) -> User | None: ...
    @abstractmethod
    async def by_email(self, email: str) -> User | None: ...
    @abstractmethod
    async def add(self, user: User) -> None: ...
    @abstractmethod
    async def save(self, user: User) -> None: ...


class TenantRepository(ABC):
    @abstractmethod
    async def get(self, tenant_id: TenantId) -> Tenant | None: ...
    @abstractmethod
    async def add(self, tenant: Tenant) -> None: ...


class MembershipRepository(ABC):
    @abstractmethod
    async def get(self, membership_id: MembershipId) -> Membership | None: ...
    @abstractmethod
    async def find(self, tenant_id: TenantId, user_id: UserId) -> Membership | None: ...
    @abstractmethod
    async def list_user(self, user_id: UserId) -> list[Membership]: ...
    @abstractmethod
    async def list_active_admins(self, tenant_id: TenantId) -> list[Membership]: ...
    @abstractmethod
    async def add(self, membership: Membership) -> None: ...
    @abstractmethod
    async def save(self, membership: Membership) -> None: ...


class InvitationRepository(ABC):
    @abstractmethod
    async def get(self, invitation_id: InvitationId) -> Invitation | None: ...
    @abstractmethod
    async def add(self, invitation: Invitation) -> None: ...
    @abstractmethod
    async def save(self, invitation: Invitation) -> None: ...


class SessionRepository(ABC):
    @abstractmethod
    async def get(self, session_id: SessionId) -> Session | None: ...
    @abstractmethod
    async def add(self, session: Session) -> None: ...
    @abstractmethod
    async def save(self, session: Session) -> None: ...


class AccessControlListRepository(ABC):
    @abstractmethod
    async def get_acl(
        self, tenant_id: TenantId, resource_type: str, resource_id: str
    ) -> AccessControlList | None: ...
    @abstractmethod
    async def list_type_acl(
        self, tenant_id: TenantId, resource_type: str
    ) -> list[AccessControlList]: ...
    @abstractmethod
    async def add(self, acl: AccessControlList) -> None: ...
    @abstractmethod
    async def save(self, acl: AccessControlList) -> None: ...
    @abstractmethod
    async def delete(self, acl: AccessControlList) -> None: ...


class GroupRepository(ABC):
    @abstractmethod
    async def get(self, group_id: GroupId) -> Group | None: ...
    @abstractmethod
    async def add(self, group: Group) -> None: ...
    @abstractmethod
    async def save(self, group: Group) -> None: ...


class GroupMembershipRepository(ABC):
    @abstractmethod
    async def get(self, membership_id: GroupMembershipId) -> GroupMembership | None: ...
    @abstractmethod
    async def add(self, membership: GroupMembership) -> None: ...
    @abstractmethod
    async def save(self, membership: GroupMembership) -> None: ...


class GroupGraph(Protocol):
    async def groups(self) -> dict[GroupId, frozenset[GroupId]]: ...


class PrincipalGroupResolver(Protocol):
    """Resolve every active direct or nested group for a user principal."""

    async def groups_for_user(self, user_id: UserId) -> frozenset[GroupId]: ...


class PrincipalStatusReadStore(Protocol):
    """Read lifecycle state without materializing a write aggregate."""

    async def is_active(self, subject: Subject) -> bool: ...


class SSOProviderRepository(ABC):
    @abstractmethod
    async def get(self, provider_id: SSOProviderId) -> SSOProvider | None: ...
    @abstractmethod
    async def by_issuer(self, issuer: str) -> SSOProvider | None: ...
    @abstractmethod
    async def add(self, provider: SSOProvider) -> None: ...
    @abstractmethod
    async def has_membership(
        self, provider_id: SSOProviderId, tenant_id: TenantId | None = None
    ) -> bool: ...
    @abstractmethod
    async def add_membership(
        self, provider_id: SSOProviderId, tenant_id: TenantId
    ) -> None: ...


class ExternalSSOIdentityRepository(ABC):
    @abstractmethod
    async def get_by_subject(
        self, provider_id: SSOProviderId, subject: str
    ) -> ExternalSSOIdentity | None: ...
    @abstractmethod
    async def add(self, identity: ExternalSSOIdentity) -> None: ...


class ServicePrincipalRepository(ABC):
    @abstractmethod
    async def get(
        self, principal_id: ServicePrincipalId
    ) -> ServicePrincipal | None: ...
    @abstractmethod
    async def add(self, principal: ServicePrincipal) -> None: ...
    @abstractmethod
    async def save(self, principal: ServicePrincipal) -> None: ...


class ApiKeyRepository(ABC):
    @abstractmethod
    async def get(self, api_key_id: ApiKeyId) -> ApiKey | None: ...
    @abstractmethod
    async def add(self, api_key: ApiKey) -> None: ...
    @abstractmethod
    async def save(self, api_key: ApiKey) -> None: ...


class AccessDecisionReadStore(Protocol):
    async def entries(
        self,
        tenant_id: TenantId,
        resource_type: str,
        resource_id: str,
        subject_id: UserId | None = None,
    ) -> list[AccessControlEntry]: ...


class MembershipReadStore(Protocol):
    async def is_active(self, tenant_id: TenantId, user_id: UserId) -> bool: ...


class MembershipListReadStore(Protocol):
    async def list_user(self, user_id: UserId) -> list[MembershipDTO]: ...
    async def list_tenant(self, tenant_id: TenantId) -> list[MembershipDTO]: ...

    async def search_tenant(
        self, tenant_id: TenantId, keyword: str, page: PageRequest
    ) -> Page[MembershipDTO]: ...


class GroupMembershipReadStore(Protocol):
    async def search_group(
        self, group_id: GroupId, keyword: str, page: PageRequest
    ) -> Page[GroupMembershipDTO]: ...


class DirectoryReadStore(Protocol):
    async def get_user(self, user_id: UserId) -> UserDTO | None: ...

    async def search_users(self, keyword: str, page: PageRequest) -> Page[UserDTO]: ...

    async def list_user_tenants(
        self, user_id: UserId, keyword: str, page: PageRequest
    ) -> Page[TenantDTO]: ...

    async def search_groups(
        self, tenant_id: TenantId, keyword: str, page: PageRequest
    ) -> Page[GroupDTO]: ...


class SessionReadStore(Protocol):
    async def get(self, session_id: SessionId) -> Session | None: ...


class AclReadStore(Protocol):
    async def get(self, scope: AclScope) -> AccessControlList | None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...
    def verify(self, password: str, password_hash: str) -> bool: ...


class OidcTokenVerifier(Protocol):
    async def verify(self, token: str) -> OidcIdentity: ...


class TokenIssuer(Protocol):
    def issue(self, claims: TokenClaims) -> IssuedToken: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class IdGenerator(Protocol):
    """Generate opaque UUID values outside the domain model."""

    def new(self) -> UUID: ...


class SessionTokenGenerator(Protocol):
    def generate(self) -> str: ...


class ApiKeySecretGenerator(Protocol):
    def generate(self) -> str: ...


class RepositoryFactories(Protocol):
    users: RepositoryFactory[UserRepository]
    tenants: RepositoryFactory[TenantRepository]
    memberships: RepositoryFactory[MembershipRepository]
    invitations: RepositoryFactory[InvitationRepository]
    sessions: RepositoryFactory[SessionRepository]
    acls: RepositoryFactory[AccessControlListRepository]


class OidcIdentity(Protocol):
    subject: str
    email: str
