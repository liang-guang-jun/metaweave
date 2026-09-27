"""IAM aggregate roots."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from ...kernel.domain.aggregate import VersionedAggregate
from .errors import IamDomainError
from .events import *
from .value_objects import *


class User(VersionedAggregate[UUID]):
    """Global user account."""

    def __init__(
        self,
        user_id: UserId,
        email: str,
        password_hash: str,
        *,
        verified: bool = False,
        active: bool = True,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        self._id, self.email, self.password_hash = (
            user_id,
            email.strip().lower(),
            password_hash,
        )
        self.verified = verified
        self.active = active
        self.failed_attempts = 0
        self.locked_until: datetime | None = None

    @property
    def id(self) -> UserId:
        return self._id

    @classmethod
    def register(cls, email: str, password_hash: str, user_id: UserId) -> User:
        user = cls(user_id, email, password_hash)
        user._record_state_change(UserRegistered(user.id, user.email))
        return user

    @classmethod
    def restore(
        cls,
        user_id: UserId,
        email: str,
        password_hash: str,
        verified: bool,
        version: int,
        active: bool = True,
    ) -> User:
        return cls(
            user_id,
            email,
            password_hash,
            verified=verified,
            active=active,
            version=version,
        )

    def verify(self) -> None:
        if self.verified:
            return
        self.verified = True
        self._record_state_change(UserVerified(self.id))

    def change_password(self, password_hash: str) -> None:
        if not password_hash:
            raise IamDomainError("password hash is required")
        self.password_hash = password_hash
        self.failed_attempts = 0
        self.locked_until = None
        self._record_state_change(PasswordChanged(self.id))

    def can_authenticate(self, now: datetime) -> bool:
        return (
            self.active
            and self.verified
            and (self.locked_until is None or self.locked_until <= now)
        )

    def disable(self) -> None:
        if not self.active:
            return
        self.active = False
        self._record_state_change(PrincipalDisabled(self.id, SubjectType.USER))

    def restore_principal(self) -> None:
        if self.active:
            return
        self.active = True
        self._record_state_change(PrincipalRestored(self.id, SubjectType.USER))

    def record_failed_login(
        self, max_attempts: int, lock_for: timedelta, now: datetime
    ) -> None:
        self.failed_attempts += 1
        if self.failed_attempts >= max_attempts:
            self.locked_until = now + lock_for


class Tenant(VersionedAggregate[UUID]):
    """Tenant aggregate."""

    def __init__(self, tenant_id: TenantId, name: str, *, version: int = 0) -> None:
        super().__init__(version=version)
        if not name.strip():
            raise IamDomainError("tenant name is required")
        self._id, self.name = tenant_id, name.strip()
        self.active = True

    @property
    def id(self) -> TenantId:
        return self._id

    @classmethod
    def create(cls, name: str, tenant_id: TenantId) -> Tenant:
        tenant = cls(tenant_id, name)
        tenant._record_state_change(TenantCreated(tenant.id, tenant.name))
        return tenant

    @classmethod
    def restore(
        cls, tenant_id: TenantId, name: str, active: bool, version: int
    ) -> Tenant:
        tenant = cls(tenant_id, name, version=version)
        tenant.active = active
        return tenant


class Membership(VersionedAggregate[UUID]):
    """A user's membership in one tenant."""

    def __init__(
        self,
        membership_id: MembershipId,
        tenant_id: TenantId,
        user_id: UserId,
        *,
        active: bool = False,
        is_admin: bool = False,
        membership_type: TenantMembershipType | None = None,
        joined_at: datetime | None = None,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        resolved_type = membership_type or (
            TenantMembershipType.ADMIN
            if is_admin
            else TenantMembershipType.MEMBER
        )
        self._id, self.tenant_id, self.user_id = membership_id, tenant_id, user_id
        self.active, self.membership_type = active, resolved_type
        self.is_admin = resolved_type in {
            TenantMembershipType.ADMIN,
            TenantMembershipType.OWNER,
        }
        self.joined_at = joined_at

    @property
    def id(self) -> MembershipId:
        return self._id

    @classmethod
    def invite(
        cls,
        tenant_id: TenantId,
        user_id: UserId,
        membership_id: MembershipId,
        *,
        admin: bool = False,
        membership_type: TenantMembershipType | None = None,
    ) -> Membership:
        membership = cls(
            membership_id,
            tenant_id,
            user_id,
            is_admin=admin,
            membership_type=membership_type,
        )
        membership._record_state_change(
            MembershipInvited(membership.id, tenant_id, user_id)
        )
        return membership

    @classmethod
    def restore(
        cls,
        membership_id: MembershipId,
        tenant_id: TenantId,
        user_id: UserId,
        active: bool,
        is_admin: bool,
        joined_at: datetime | None,
        version: int,
        membership_type: TenantMembershipType | None = None,
    ) -> Membership:
        return cls(
            membership_id,
            tenant_id,
            user_id,
            active=active,
            is_admin=is_admin,
            membership_type=membership_type,
            joined_at=joined_at,
            version=version,
        )

    def accept(self, now: datetime) -> None:
        if self.active:
            return
        self.active, self.joined_at = True, now
        self._record_state_change(MembershipAccepted(self.id))

    def remove(self) -> None:
        if not self.active:
            return
        self.active = False
        self._record_state_change(MembershipRemoved(self.id))

    def restore_membership(self, now: datetime | None = None) -> None:
        if self.active:
            return
        self.active = True
        if now is not None:
            self.joined_at = now
        self._record_state_change(MembershipRestored(self.id))

    def promote(self) -> None:
        if self.is_admin:
            return
        self.membership_type = TenantMembershipType.ADMIN
        self.is_admin = True
        self._record_state_change(MembershipPromoted(self.id))

    def demote(self) -> None:
        if not self.is_admin:
            return
        self.membership_type = TenantMembershipType.MEMBER
        self.is_admin = False
        self._record_state_change(MembershipDemoted(self.id))


class Group(VersionedAggregate[UUID]):
    """Tenant-local group whose members can be users or nested groups."""

    def __init__(
        self,
        group_id: GroupId,
        tenant_id: TenantId,
        name: str,
        members: frozenset[UserId | GroupId] = frozenset(),
        *,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        if not name.strip():
            raise IamDomainError("group name is required")
        self._id, self.tenant_id, self.name, self.members = (
            group_id,
            tenant_id,
            name.strip(),
            members,
        )

    @property
    def id(self) -> GroupId:
        return self._id

    @classmethod
    def create(cls, group_id: GroupId, tenant_id: TenantId, name: str) -> Group:
        group = cls(group_id, tenant_id, name)
        group._record_state_change(GroupCreated(group.id, tenant_id, group.name))
        return group

    @classmethod
    def restore(
        cls,
        group_id: GroupId,
        tenant_id: TenantId,
        name: str,
        members: frozenset[UserId | GroupId],
        version: int,
    ) -> Group:
        return cls(group_id, tenant_id, name, members, version=version)

    def add_member(self, member_id: UserId | GroupId) -> None:
        if member_id == self.id:
            raise IamDomainError("a group cannot contain itself")
        if member_id in self.members:
            return
        self.members = self.members | {member_id}
        self._record_state_change(GroupMemberAdded(self.id, member_id))

    def remove_member(self, member_id: UserId | GroupId) -> None:
        if member_id not in self.members:
            return
        self.members = self.members - {member_id}
        self._record_state_change(GroupMemberRemoved(self.id, member_id))


class GroupMembership(VersionedAggregate[UUID]):
    """Explicit group membership, distinct from tenant membership."""

    def __init__(
        self,
        membership_id: GroupMembershipId,
        group_id: GroupId,
        member_id: UserId | GroupId,
        *,
        member_type: GroupMemberType | None = None,
        active: bool = True,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        if group_id == member_id:
            raise IamDomainError("a group cannot contain itself")
        resolved_type = member_type or (
            GroupMemberType.GROUP
            if isinstance(member_id, GroupId)
            else GroupMemberType.USER
        )
        if resolved_type is GroupMemberType.OWNER and not isinstance(member_id, UserId):
            raise IamDomainError("group owner must be a user")
        self._id, self.group_id, self.member_id, self.member_type, self.active = (
            membership_id,
            group_id,
            member_id,
            resolved_type,
            active,
        )

    @property
    def id(self) -> GroupMembershipId:
        return self._id

    @classmethod
    def create(
        cls,
        membership_id: GroupMembershipId,
        group_id: GroupId,
        member_id: UserId | GroupId,
        member_type: GroupMemberType | None = None,
    ) -> GroupMembership:
        membership = cls(
            membership_id, group_id, member_id, member_type=member_type
        )
        membership._record_state_change(
            GroupMembershipCreated(
                membership.id, group_id, member_id, membership.member_type
            )
        )
        return membership

    @classmethod
    def restore(
        cls,
        membership_id: GroupMembershipId,
        group_id: GroupId,
        member_id: UserId | GroupId,
        active: bool,
        version: int,
        member_type: GroupMemberType | None = None,
    ) -> GroupMembership:
        return cls(
            membership_id,
            group_id,
            member_id,
            member_type=member_type,
            active=active,
            version=version,
        )

    def remove(self) -> None:
        if self.active:
            self.active = False
            self._record_state_change(GroupMembershipRemoved(self.id))

    def restore_membership(self) -> None:
        if not self.active:
            self.active = True
            self._record_state_change(GroupMembershipRestored(self.id))


class SSOProvider(VersionedAggregate[UUID]):
    """Tenant OIDC provider configuration; secrets remain infrastructure-owned."""

    def __init__(
        self,
        provider_id: SSOProviderId,
        tenant_id: TenantId,
        issuer: str,
        client_id: str,
        client_secret: str,
        *,
        active: bool = True,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        if not issuer.strip() or not client_id.strip() or not client_secret.strip():
            raise IamDomainError("SSO issuer, client id and secret are required")
        self._id, self.tenant_id, self.issuer, self.client_id, self.client_secret, self.active = (
            provider_id,
            tenant_id,
            issuer.strip(),
            client_id.strip(),
            client_secret,
            active,
        )

    @property
    def id(self) -> SSOProviderId:
        return self._id

    @classmethod
    def configure(
        cls,
        provider_id: SSOProviderId,
        tenant_id: TenantId,
        issuer: str,
        client_id: str,
        client_secret: str,
    ) -> SSOProvider:
        provider = cls(provider_id, tenant_id, issuer, client_id, client_secret)
        provider._record_state_change(
            SSOProviderConfigured(provider.id, tenant_id, provider.issuer)
        )
        return provider


class ExternalSSOIdentity(VersionedAggregate[UUID]):
    """Stable association between a local user and a verified external subject."""

    def __init__(
        self,
        identity_id: ExternalSSOIdentityId,
        user_id: UserId,
        provider_id: SSOProviderId,
        external_subject: str,
        *,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        if not external_subject.strip():
            raise IamDomainError("external subject is required")
        self._id, self.user_id, self.provider_id, self.external_subject = (
            identity_id,
            user_id,
            provider_id,
            external_subject.strip(),
        )

    @property
    def id(self) -> ExternalSSOIdentityId:
        return self._id

    @classmethod
    def link(
        cls,
        identity_id: ExternalSSOIdentityId,
        user_id: UserId,
        provider_id: SSOProviderId,
        external_subject: str,
    ) -> ExternalSSOIdentity:
        identity = cls(identity_id, user_id, provider_id, external_subject)
        identity._record_state_change(
            ExternalSSOIdentityLinked(identity.id, user_id, provider_id)
        )
        return identity


class ServicePrincipal(VersionedAggregate[UUID]):
    """Tenant workload identity authenticated through hashed API keys."""

    def __init__(
        self,
        principal_id: ServicePrincipalId,
        tenant_id: TenantId,
        name: str,
        *,
        active: bool = True,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        if not name.strip():
            raise IamDomainError("service principal name is required")
        self._id, self.tenant_id, self.name, self.active = (
            principal_id,
            tenant_id,
            name.strip(),
            active,
        )

    @property
    def id(self) -> ServicePrincipalId:
        return self._id

    @classmethod
    def create(
        cls, principal_id: ServicePrincipalId, tenant_id: TenantId, name: str
    ) -> ServicePrincipal:
        principal = cls(principal_id, tenant_id, name)
        principal._record_state_change(
            ServicePrincipalCreated(principal.id, tenant_id, principal.name)
        )
        return principal

    @classmethod
    def restore(
        cls,
        principal_id: ServicePrincipalId,
        tenant_id: TenantId,
        name: str,
        active: bool,
        version: int,
    ) -> ServicePrincipal:
        return cls(
            principal_id,
            tenant_id,
            name,
            active=active,
            version=version,
        )

    def disable(self) -> None:
        if not self.active:
            return
        self.active = False
        self._record_state_change(
            PrincipalDisabled(self.id, SubjectType.SERVICE_PRINCIPAL)
        )

    def restore_principal(self) -> None:
        if self.active:
            return
        self.active = True
        self._record_state_change(
            PrincipalRestored(self.id, SubjectType.SERVICE_PRINCIPAL)
        )


class ApiKey(VersionedAggregate[UUID]):
    """Hashed, revocable credential belonging to one service principal."""

    def __init__(
        self,
        api_key_id: ApiKeyId,
        principal_id: ServicePrincipalId,
        secret_hash: str,
        *,
        revoked: bool = False,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        if not secret_hash:
            raise IamDomainError("API key hash is required")
        self._id, self.principal_id, self.secret_hash, self.revoked = (
            api_key_id,
            principal_id,
            secret_hash,
            revoked,
        )

    @property
    def id(self) -> ApiKeyId:
        return self._id

    @classmethod
    def issue(
        cls, api_key_id: ApiKeyId, principal_id: ServicePrincipalId, secret_hash: str
    ) -> ApiKey:
        key = cls(api_key_id, principal_id, secret_hash)
        key._record_state_change(ApiKeyIssued(key.id, principal_id))
        return key

    def revoke(self) -> None:
        if not self.revoked:
            self.revoked = True
            self._record_state_change(ApiKeyRevoked(self.id))


class Invitation(VersionedAggregate[UUID]):
    """Invitation to join a tenant."""

    def __init__(
        self,
        invitation_id: InvitationId,
        tenant_id: TenantId,
        user_id: UserId,
        token_hash: str,
        expires_at: datetime,
        *,
        accepted: bool = False,
        revoked: bool = False,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        self._id, self.tenant_id, self.user_id = invitation_id, tenant_id, user_id
        self.token_hash, self.expires_at = token_hash, expires_at
        self.accepted, self.revoked = accepted, revoked

    @property
    def id(self) -> InvitationId:
        return self._id

    @classmethod
    def restore(
        cls,
        invitation_id: InvitationId,
        tenant_id: TenantId,
        user_id: UserId,
        token_hash: str,
        expires_at: datetime,
        accepted: bool,
        revoked: bool,
        version: int,
    ) -> Invitation:
        return cls(
            invitation_id,
            tenant_id,
            user_id,
            token_hash,
            expires_at,
            accepted=accepted,
            revoked=revoked,
            version=version,
        )

    def accept(self, now: datetime) -> None:
        if self.accepted or self.revoked or self.expires_at <= now:
            raise IamDomainError("invitation is not valid")
        self.accepted = True

    def revoke(self) -> None:
        self.revoked = True


class Session(VersionedAggregate[UUID]):
    """Revocable login session."""

    def __init__(
        self,
        session_id: SessionId,
        user_id: UserId,
        tenant_id: TenantId,
        expires_at: datetime,
        *,
        revoked: bool = False,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        self._id, self.user_id, self.tenant_id = session_id, user_id, tenant_id
        self.expires_at, self.revoked = expires_at, revoked

    @property
    def id(self) -> SessionId:
        return self._id

    @classmethod
    def create(
        cls,
        user_id: UserId,
        tenant_id: TenantId,
        expires_at: datetime,
        session_id: SessionId,
    ) -> Session:
        session = cls(session_id, user_id, tenant_id, expires_at)
        session._record_state_change(SessionCreated(session.id, user_id, tenant_id))
        return session

    @classmethod
    def restore(
        cls,
        session_id: SessionId,
        user_id: UserId,
        tenant_id: TenantId,
        expires_at: datetime,
        revoked: bool,
        version: int,
    ) -> Session:
        return cls(
            session_id, user_id, tenant_id, expires_at, revoked=revoked, version=version
        )

    def revoke(self) -> None:
        if not self.revoked:
            self.revoked = True
            self._record_state_change(SessionRevoked(self.id))

    def is_valid(self, now: datetime) -> bool:
        return not self.revoked and self.expires_at > now


class AccessControlList(VersionedAggregate[UUID]):
    """ACL aggregate for one tenant/resource scope."""

    def __init__(
        self,
        acl_id: AclId,
        scope: AclScope,
        entries: tuple[AccessControlEntry, ...] = (),
        *,
        version: int = 0,
    ) -> None:
        super().__init__(version=version)
        self._id, self.scope = acl_id, scope
        self.entries: dict[tuple[Subject, Action | IAMRole], AccessControlEntry] = {
            (entry.subject, entry.action): entry for entry in entries
        }

    @property
    def id(self) -> AclId:
        return self._id

    @classmethod
    def register(cls, scope: AclScope, acl_id: AclId) -> AccessControlList:
        acl = cls(acl_id, scope)
        acl._record_state_change(AclRegistered(acl.id, scope))
        return acl

    @classmethod
    def restore(
        cls,
        acl_id: AclId,
        scope: AclScope,
        entries: tuple[AccessControlEntry, ...],
        version: int,
    ) -> AccessControlList:
        return cls(acl_id, scope, entries, version=version)

    def grant(
        self, subject: Subject, action: Action | IAMRole, effect: Effect = Effect.ALLOW
    ) -> None:
        entry = AccessControlEntry(subject, action, effect)
        previous = self.entries.get((subject, action))
        if previous == entry:
            return
        self.entries[(subject, action)] = entry
        event_type = AccessGranted if effect is Effect.ALLOW else AccessRevoked
        self._record_state_change(event_type(self.id, self.scope, entry))

    def revoke(self, subject: Subject, action: Action | IAMRole) -> None:
        self.grant(subject, action, Effect.DENY)

    def remove(self, subject: Subject, action: Action | IAMRole) -> None:
        """Remove a relationship-managed entry instead of creating a DENY."""
        entry = self.entries.pop((subject, action), None)
        if entry is not None:
            self._record_state_change(AccessRemoved(self.id, self.scope, entry))

    def delete(self) -> None:
        self._record_state_change(AclDeleted(self.id, self.scope))
