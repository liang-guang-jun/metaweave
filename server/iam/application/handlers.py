"""IAM command and query handlers."""
# mypy: ignore-errors

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from ...kernel.application.context import current_context_or_none
from ...kernel.application.common.page import Page
from ...kernel.application.messaging.handler import CommandHandler, QueryHandler
from ...kernel.application.unit_of_work import UnitOfWork
from ..domain.entities import (
    AccessControlList,
    Invitation,
    Membership,
    Session,
    Tenant,
    User,
)
from ..domain.errors import IamDomainError
from ..domain.services import (
    AccessDecision,
    AccessDecisionEvaluator,
    GroupNestingGuard,
    LastAdminGuard,
    PasswordPolicyValidator,
)
from ..domain.value_objects import *
from .dto import *
from .messages import *
from .permissions import (
    RelationshipAclSynchronizer,
    group_role_action,
    group_subject,
    tenant_role_action,
    tenant_subject,
)
from .ports import *


def _require_uow(uow: UnitOfWork | None) -> UnitOfWork:
    if uow is None:
        raise RuntimeError("IAM command requires an active UnitOfWork")
    return uow


def _actor() -> UserId | None:
    context = current_context_or_none()
    value = context.metadata.user_id if context else None
    return UserId(value) if value else None


async def _require_admin(
    memberships: RepositoryFactory[MembershipRepository],
    uow: UnitOfWork,
    tenant_id: TenantId,
    permissions: RelationshipAclSynchronizer | None = None,
) -> None:
    actor = _actor()
    if actor is None:
        raise IamDomainError("active administrator context required")
    membership = await memberships(uow).find(tenant_id, actor)
    if membership is None or not membership.active:
        raise IamDomainError("active administrator context required")
    if permissions is not None:
        if not await permissions.has_tenant_admin_access(uow, tenant_id, actor):
            raise IamDomainError("active administrator context required")
        return
    if not membership.is_admin:
        raise IamDomainError("active administrator context required")


class RegisterUserHandler(CommandHandler[RegisterUser, UserId]):
    def __init__(
        self,
        users: RepositoryFactory[UserRepository],
        hasher: PasswordHasher,
        policy: PasswordPolicyValidator,
        ids: IdGenerator,
    ) -> None:
        self.users, self.hasher, self.policy, self.ids = users, hasher, policy, ids

    async def handle(
        self, message: RegisterUser, uow: UnitOfWork | None = None
    ) -> UserId:
        transaction = _require_uow(uow)
        self.policy.validate(message.password)
        repo = self.users(transaction)
        if await repo.by_email(message.email) is not None:
            raise IamDomainError("email is already registered")
        user = User.register(
            message.email, self.hasher.hash(message.password), UserId(self.ids.new())
        )
        await repo.add(user)
        return user.id


class BootstrapSystemAdminHandler(CommandHandler[BootstrapSystemAdmin, UserId]):
    """Create the initial instance administrator inside one transaction."""

    def __init__(
        self,
        users: RepositoryFactory[UserRepository],
        hasher: PasswordHasher,
        policy: PasswordPolicyValidator,
        ids: IdGenerator,
        permissions: RelationshipAclSynchronizer,
    ) -> None:
        self.users = users
        self.hasher = hasher
        self.policy = policy
        self.ids = ids
        self.permissions = permissions

    async def handle(
        self, message: BootstrapSystemAdmin, uow: UnitOfWork | None = None
    ) -> UserId:
        transaction = _require_uow(uow)
        self.policy.validate(message.password)
        users = self.users(transaction)
        if await users.by_email(message.email) is not None:
            raise IamDomainError("email is already registered")

        if await self.permissions.has_any_system_admin(transaction):
            raise IamDomainError("an active system administrator already exists")

        user = User.register(
            message.email,
            self.hasher.hash(message.password),
            UserId(self.ids.new()),
        )
        # A local administrator is an explicit bootstrap credential, not an
        # email-verification workflow participant.
        user.verify()
        await users.add(user)

        await self.permissions.grant_system_role(
            transaction, tenant_subject(user.id), SystemAdminRole.SUPER_ADMIN
        )
        return user.id


class VerifyUserHandler(CommandHandler[VerifyUser, None]):
    def __init__(self, users: RepositoryFactory[UserRepository]) -> None:
        self.users = users

    async def handle(self, message: VerifyUser, uow: UnitOfWork | None = None) -> None:
        repo = self.users(_require_uow(uow))
        user = await repo.get(message.user_id)
        if user is None:
            raise IamDomainError("user not found")
        user.verify()
        await repo.save(user)


class ChangePasswordHandler(CommandHandler[ChangePassword, None]):
    def __init__(
        self,
        users: RepositoryFactory[UserRepository],
        hasher: PasswordHasher,
        policy: PasswordPolicyValidator,
    ) -> None:
        self.users, self.hasher, self.policy = users, hasher, policy

    async def handle(
        self, message: ChangePassword, uow: UnitOfWork | None = None
    ) -> None:
        self.policy.validate(message.password)
        repo = self.users(_require_uow(uow))
        user = await repo.get(message.user_id)
        if user is None:
            raise IamDomainError("user not found")
        user.change_password(self.hasher.hash(message.password))
        await repo.save(user)


class _PrincipalLifecycleHandler(CommandHandler):
    """Common authorization and aggregate lookup for principal lifecycle changes."""

    def __init__(
        self,
        users: RepositoryFactory[UserRepository],
        principals: RepositoryFactory[ServicePrincipalRepository],
        memberships: RepositoryFactory[MembershipRepository],
        permissions: RelationshipAclSynchronizer,
    ) -> None:
        self.users = users
        self.principals = principals
        self.memberships = memberships
        self.permissions = permissions

    async def _principal(
        self, subject: Subject, uow: UnitOfWork
    ) -> tuple[User | ServicePrincipal, UserRepository | ServicePrincipalRepository]:
        if subject.subject_type is SubjectType.USER:
            actor = _actor()
            if actor is None or not await self.permissions.has_system_admin_access(
                uow, actor
            ):
                raise IamDomainError("system administrator context required")
            user = await self.users(uow).get(UserId(subject.subject_id.value))
            if user is None:
                raise IamDomainError("user not found")
            return user, self.users(uow)

        if subject.subject_type is SubjectType.SERVICE_PRINCIPAL:
            principal = await self.principals(uow).get(
                ServicePrincipalId(subject.subject_id.value)
            )
            if principal is None:
                raise IamDomainError("service principal not found")
            await _require_admin(
                self.memberships, uow, principal.tenant_id, self.permissions
            )
            return principal, self.principals(uow)

        raise IamDomainError("principal lifecycle is not supported for this subject")


class DisablePrincipalHandler(
    _PrincipalLifecycleHandler, CommandHandler[DisablePrincipal, None]
):
    async def handle(
        self, message: DisablePrincipal, uow: UnitOfWork | None = None
    ) -> None:
        transaction = _require_uow(uow)
        principal, repository = await self._principal(message.subject, transaction)
        principal.disable()
        await repository.save(principal)


class RestorePrincipalHandler(
    _PrincipalLifecycleHandler, CommandHandler[RestorePrincipal, None]
):
    async def handle(
        self, message: RestorePrincipal, uow: UnitOfWork | None = None
    ) -> None:
        transaction = _require_uow(uow)
        principal, repository = await self._principal(message.subject, transaction)
        principal.restore_principal()
        await repository.save(principal)


class CreateTenantHandler(CommandHandler[CreateTenant, TenantId]):
    def __init__(
        self,
        tenants: RepositoryFactory[TenantRepository],
        memberships: RepositoryFactory[MembershipRepository],
        ids: IdGenerator,
        clock: Clock,
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.tenants, self.memberships, self.ids, self.clock, self.permissions = (
            tenants,
            memberships,
            ids,
            clock,
            permissions,
        )

    async def handle(
        self, message: CreateTenant, uow: UnitOfWork | None = None
    ) -> TenantId:
        transaction = _require_uow(uow)
        tenant = Tenant.create(message.name, TenantId(self.ids.new()))
        await self.tenants(transaction).add(tenant)
        if message.owner_user_id:
            membership = Membership.invite(
                tenant.id,
                message.owner_user_id,
                MembershipId(self.ids.new()),
                admin=True,
                membership_type=TenantMembershipType.OWNER,
            )
            membership.accept(self.clock.now())
            await self.memberships(transaction).add(membership)
            if self.permissions is not None:
                await self.permissions.grant(
                    transaction,
                    tenant.id,
                    "tenant",
                    str(tenant.id),
                    tenant_subject(membership.user_id),
                    tenant_role_action(membership.membership_type),
                )
        return tenant.id


class GrantSystemAdminHandler(CommandHandler[GrantSystemAdmin, None]):
    def __init__(
        self,
        permissions: RelationshipAclSynchronizer,
    ) -> None:
        self.permissions = permissions

    async def handle(
        self, message: GrantSystemAdmin, uow: UnitOfWork | None = None
    ) -> None:
        transaction = _require_uow(uow)
        actor = _actor()
        if actor is None or not await self.permissions.has_system_admin_access(
            transaction, actor
        ):
            raise IamDomainError("system administrator context required")
        await self.permissions.grant_system_role(
            transaction, message.subject, SystemAdminRole.SUPER_ADMIN
        )


class RevokeSystemAdminHandler(CommandHandler[RevokeSystemAdmin, None]):
    def __init__(
        self,
        permissions: RelationshipAclSynchronizer,
    ) -> None:
        self.permissions = permissions

    async def handle(
        self, message: RevokeSystemAdmin, uow: UnitOfWork | None = None
    ) -> None:
        transaction = _require_uow(uow)
        actor = _actor()
        if actor is None or not await self.permissions.has_system_admin_access(
            transaction, actor
        ):
            raise IamDomainError("system administrator context required")
        await self.permissions.remove_system_role(
            transaction, message.subject, SystemAdminRole.SUPER_ADMIN
        )


class InviteMemberHandler(CommandHandler[InviteMember, MembershipId]):
    def __init__(
        self,
        memberships: RepositoryFactory[MembershipRepository],
        ids: IdGenerator,
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.memberships, self.ids, self.permissions = memberships, ids, permissions

    async def handle(
        self, message: InviteMember, uow: UnitOfWork | None = None
    ) -> MembershipId:
        transaction = _require_uow(uow)
        # The database also enforces this invariant, but checking before the
        # insert gives callers a stable domain-level conflict instead of an
        # opaque IntegrityError at commit time.
        repo = self.memberships(transaction)
        await _require_admin(
            self.memberships, transaction, message.tenant_id, self.permissions
        )
        if await repo.find(message.tenant_id, message.user_id) is not None:
            raise IamDomainError("membership already exists")
        membership = Membership.invite(
            message.tenant_id,
            message.user_id,
            MembershipId(self.ids.new()),
            admin=message.is_admin,
            membership_type=message.membership_type
            or (
                TenantMembershipType.ADMIN
                if message.is_admin
                else TenantMembershipType.MEMBER
            ),
        )
        await repo.add(membership)
        if self.permissions is not None:
            await self.permissions.grant(
                transaction,
                membership.tenant_id,
                "tenant",
                str(membership.tenant_id),
                tenant_subject(membership.user_id),
                tenant_role_action(membership.membership_type),
            )
        return membership.id


class AcceptInvitationHandler(CommandHandler[AcceptInvitation, None]):
    def __init__(
        self,
        memberships: RepositoryFactory[MembershipRepository],
        clock: Clock,
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.memberships, self.clock, self.permissions = memberships, clock, permissions

    async def handle(
        self, message: AcceptInvitation, uow: UnitOfWork | None = None
    ) -> None:
        repo = self.memberships(_require_uow(uow))
        membership = await repo.get(message.membership_id)
        if membership is None:
            raise IamDomainError("membership not found")
        membership.accept(self.clock.now())
        await repo.save(membership)
        if self.permissions is not None:
            await self.permissions.grant(
                _require_uow(uow),
                membership.tenant_id,
                "tenant",
                str(membership.tenant_id),
                tenant_subject(membership.user_id),
                tenant_role_action(membership.membership_type),
            )


class CreateGroupHandler(CommandHandler[CreateGroup, GroupId]):
    def __init__(
        self,
        groups: RepositoryFactory[GroupRepository],
        ids: IdGenerator,
        memberships_repo: RepositoryFactory[MembershipRepository],
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.groups, self.ids, self.memberships_repo, self.permissions = (
            groups,
            ids,
            memberships_repo,
            permissions,
        )

    async def handle(
        self, message: CreateGroup, uow: UnitOfWork | None = None
    ) -> GroupId:
        transaction = _require_uow(uow)
        await _require_admin(
            self.memberships_repo, transaction, message.tenant_id, self.permissions
        )
        owner = _actor()
        if owner is None:
            raise IamDomainError("active administrator context required")
        group = Group.create(GroupId(self.ids.new()), message.tenant_id, message.name)
        group.add_member(owner)
        await self.groups(transaction).add(group)
        owner_membership = GroupMembership.create(
            GroupMembershipId(self.ids.new()),
            group.id,
            owner,
            member_type=GroupMemberType.OWNER,
        )
        await self.memberships(transaction).add(owner_membership)
        if self.permissions is not None:
            await self.permissions.grant(
                transaction,
                group.tenant_id,
                "group",
                str(group.id),
                group_subject(owner),
                group_role_action(owner_membership.member_type),
            )
        return group.id


class AddGroupMemberHandler(CommandHandler[AddGroupMember, None]):
    def __init__(
        self,
        groups: RepositoryFactory[GroupRepository],
        memberships: RepositoryFactory[GroupMembershipRepository],
        ids: IdGenerator,
        group_graph: GroupGraph,
        memberships_repo: RepositoryFactory[MembershipRepository],
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        (
            self.groups,
            self.memberships,
            self.ids,
            self.group_graph,
            self.memberships_repo,
            self.permissions,
        ) = (
            groups,
            memberships,
            ids,
            group_graph,
            memberships_repo,
            permissions,
        )

    async def handle(
        self, message: AddGroupMember, uow: UnitOfWork | None = None
    ) -> None:
        transaction = _require_uow(uow)
        group = await self.groups(transaction).get(message.group_id)
        if group is None:
            raise IamDomainError("group not found")
        await _require_admin(
            self.memberships_repo, transaction, group.tenant_id, self.permissions
        )
        if isinstance(message.member_id, GroupId):
            GroupNestingGuard.ensure_acyclic(
                group.id, message.member_id, await self.group_graph.groups()
            )
        group.add_member(message.member_id)
        await self.groups(transaction).save(group)
        membership = GroupMembership.create(
            GroupMembershipId(self.ids.new()),
            group.id,
            message.member_id,
            member_type=message.member_type,
        )
        await self.memberships(transaction).add(membership)
        if self.permissions is not None:
            await self.permissions.grant(
                transaction,
                group.tenant_id,
                "group",
                str(group.id),
                group_subject(message.member_id),
                group_role_action(membership.member_type),
            )


class RemoveGroupMemberHandler(CommandHandler[RemoveGroupMember, None]):
    def __init__(
        self,
        memberships: RepositoryFactory[GroupMembershipRepository],
        groups: RepositoryFactory[GroupRepository],
        tenant_memberships: RepositoryFactory[MembershipRepository],
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.memberships = memberships
        self.groups = groups
        self.tenant_memberships = tenant_memberships
        self.permissions = permissions

    async def handle(
        self, message: RemoveGroupMember, uow: UnitOfWork | None = None
    ) -> None:
        transaction = _require_uow(uow)
        repo = self.memberships(transaction)
        membership = await repo.get(message.membership_id)
        if membership is None:
            raise IamDomainError("group membership not found")
        if message.group_id is not None and membership.group_id != message.group_id:
            raise IamDomainError("group membership does not belong to group")
        group = await self.groups(transaction).get(membership.group_id)
        if group is None:
            raise IamDomainError("group not found")
        await _require_admin(
            self.tenant_memberships, transaction, group.tenant_id, self.permissions
        )
        membership.remove()
        group.remove_member(membership.member_id)
        await self.groups(transaction).save(group)
        await repo.save(membership)
        if self.permissions is not None:
            await self.permissions.remove(
                transaction,
                group.tenant_id,
                "group",
                str(group.id),
                group_subject(membership.member_id),
                group_role_action(membership.member_type),
            )


class RestoreGroupMemberHandler(CommandHandler[RestoreGroupMember, None]):
    def __init__(
        self,
        memberships: RepositoryFactory[GroupMembershipRepository],
        groups: RepositoryFactory[GroupRepository],
        tenant_memberships: RepositoryFactory[MembershipRepository],
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.memberships = memberships
        self.groups = groups
        self.tenant_memberships = tenant_memberships
        self.permissions = permissions

    async def handle(
        self, message: RestoreGroupMember, uow: UnitOfWork | None = None
    ) -> None:
        transaction = _require_uow(uow)
        repo = self.memberships(transaction)
        membership = await repo.get(message.membership_id)
        if membership is None:
            raise IamDomainError("group membership not found")
        if message.group_id is not None and membership.group_id != message.group_id:
            raise IamDomainError("group membership does not belong to group")
        group = await self.groups(transaction).get(membership.group_id)
        if group is None:
            raise IamDomainError("group not found")
        await _require_admin(
            self.tenant_memberships, transaction, group.tenant_id, self.permissions
        )
        membership.restore_membership()
        group.add_member(membership.member_id)
        await self.groups(transaction).save(group)
        await repo.save(membership)
        if self.permissions is not None:
            await self.permissions.grant(
                transaction,
                group.tenant_id,
                "group",
                str(group.id),
                group_subject(membership.member_id),
                group_role_action(membership.member_type),
            )


class ConfigureSSOProviderHandler(CommandHandler[ConfigureSSOProvider, SSOProviderId]):
    def __init__(
        self,
        providers: RepositoryFactory[SSOProviderRepository],
        memberships: RepositoryFactory[MembershipRepository],
        ids: IdGenerator,
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.providers, self.memberships, self.ids, self.permissions = (
            providers,
            memberships,
            ids,
            permissions,
        )

    async def handle(
        self, message: ConfigureSSOProvider, uow: UnitOfWork | None = None
    ) -> SSOProviderId:
        transaction = _require_uow(uow)
        await _require_admin(
            self.memberships, transaction, message.tenant_id, self.permissions
        )
        provider = SSOProvider.configure(
            SSOProviderId(self.ids.new()),
            message.tenant_id,
            message.issuer,
            message.client_id,
            message.client_secret,
        )
        await self.providers(transaction).add(provider)
        return provider.id


class LinkExternalSSOIdentityHandler(
    CommandHandler[LinkExternalSSOIdentity, ExternalSSOIdentityId]
):
    def __init__(
        self,
        providers: RepositoryFactory[SSOProviderRepository],
        identities: RepositoryFactory[ExternalSSOIdentityRepository],
        memberships: RepositoryFactory[MembershipRepository],
        ids: IdGenerator,
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.providers, self.identities, self.memberships, self.ids = (
            providers,
            identities,
            memberships,
            ids,
        )
        self.permissions = permissions

    async def handle(
        self, message: LinkExternalSSOIdentity, uow: UnitOfWork | None = None
    ) -> ExternalSSOIdentityId:
        transaction = _require_uow(uow)
        providers = self.providers(transaction)
        provider = await providers.get(message.provider_id)
        if provider is None or not provider.active:
            raise IamDomainError("SSO provider not found")
        await _require_admin(
            self.memberships, transaction, provider.tenant_id, self.permissions
        )
        identities = self.identities(transaction)
        if await identities.get_by_subject(provider.id, message.external_subject):
            raise IamDomainError("external identity is already linked")
        identity = ExternalSSOIdentity.link(
            ExternalSSOIdentityId(self.ids.new()),
            message.user_id,
            provider.id,
            message.external_subject,
        )
        await identities.add(identity)
        return identity.id


class CreateServicePrincipalHandler(
    CommandHandler[CreateServicePrincipal, ServicePrincipalId]
):
    def __init__(
        self,
        principals: RepositoryFactory[ServicePrincipalRepository],
        memberships: RepositoryFactory[MembershipRepository],
        ids: IdGenerator,
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.principals, self.memberships, self.ids, self.permissions = (
            principals,
            memberships,
            ids,
            permissions,
        )

    async def handle(
        self, message: CreateServicePrincipal, uow: UnitOfWork | None = None
    ) -> ServicePrincipalId:
        transaction = _require_uow(uow)
        await _require_admin(
            self.memberships, transaction, message.tenant_id, self.permissions
        )
        principal = ServicePrincipal.create(
            ServicePrincipalId(self.ids.new()), message.tenant_id, message.name
        )
        await self.principals(transaction).add(principal)
        return principal.id


class IssueApiKeyHandler(CommandHandler[IssueApiKey, tuple[ApiKeyId, str]]):
    def __init__(
        self,
        principals: RepositoryFactory[ServicePrincipalRepository],
        keys: RepositoryFactory[ApiKeyRepository],
        memberships: RepositoryFactory[MembershipRepository],
        hasher: PasswordHasher,
        secrets: ApiKeySecretGenerator,
        ids: IdGenerator,
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.principals, self.keys, self.memberships = principals, keys, memberships
        self.hasher, self.secrets, self.ids = hasher, secrets, ids
        self.permissions = permissions

    async def handle(
        self, message: IssueApiKey, uow: UnitOfWork | None = None
    ) -> tuple[ApiKeyId, str]:
        transaction = _require_uow(uow)
        principal = await self.principals(transaction).get(message.principal_id)
        if principal is None or not principal.active:
            raise IamDomainError("service principal not found")
        await _require_admin(
            self.memberships, transaction, principal.tenant_id, self.permissions
        )
        secret = self.secrets.generate()
        key = ApiKey.issue(
            ApiKeyId(self.ids.new()), principal.id, self.hasher.hash(secret)
        )
        await self.keys(transaction).add(key)
        return key.id, secret


class RevokeApiKeyHandler(CommandHandler[RevokeApiKey, None]):
    def __init__(
        self,
        principals: RepositoryFactory[ServicePrincipalRepository],
        keys: RepositoryFactory[ApiKeyRepository],
        memberships: RepositoryFactory[MembershipRepository],
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.principals, self.keys, self.memberships, self.permissions = (
            principals,
            keys,
            memberships,
            permissions,
        )

    async def handle(
        self, message: RevokeApiKey, uow: UnitOfWork | None = None
    ) -> None:
        transaction = _require_uow(uow)
        keys = self.keys(transaction)
        key = await keys.get(message.api_key_id)
        if key is None:
            return
        principal = await self.principals(transaction).get(key.principal_id)
        if principal is None:
            raise IamDomainError("service principal not found")
        await _require_admin(
            self.memberships, transaction, principal.tenant_id, self.permissions
        )
        key.revoke()
        await keys.save(key)


class _MembershipMutation(CommandHandler):
    def __init__(
        self,
        memberships: RepositoryFactory[MembershipRepository],
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.memberships = memberships
        self.permissions = permissions

    async def _get(
        self, message: object, uow: UnitOfWork | None
    ) -> tuple[MembershipRepository, Membership]:
        membership_id = getattr(message, "membership_id")
        repo = self.memberships(_require_uow(uow))
        membership = await repo.get(membership_id)
        if membership is None:
            raise IamDomainError("membership not found")
        await _require_admin(
            self.memberships,
            _require_uow(uow),
            membership.tenant_id,
            self.permissions,
        )
        return repo, membership


class RemoveMemberHandler(_MembershipMutation, CommandHandler[RemoveMember, None]):
    async def handle(
        self, message: RemoveMember, uow: UnitOfWork | None = None
    ) -> None:
        repo, membership = await self._get(message, uow)
        admins = await repo.list_active_admins(membership.tenant_id)
        LastAdminGuard.ensure_not_last_admin(
            removing_admin=membership.active and membership.is_admin,
            active_admin_count=len(admins),
        )
        membership.remove()
        await repo.save(membership)
        if self.permissions is not None:
            await self.permissions.remove(
                _require_uow(uow),
                membership.tenant_id,
                "tenant",
                str(membership.tenant_id),
                tenant_subject(membership.user_id),
                tenant_role_action(membership.membership_type),
            )


class DisableMembershipHandler(
    RemoveMemberHandler, CommandHandler[DisableMembership, None]
):
    """Disable a tenant membership while keeping it restorable."""


class RestoreMembershipHandler(
    _MembershipMutation, CommandHandler[RestoreMembership, None]
):
    def __init__(
        self,
        memberships: RepositoryFactory[MembershipRepository],
        clock: Clock,
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        super().__init__(memberships, permissions)
        self.clock = clock

    async def handle(
        self, message: RestoreMembership, uow: UnitOfWork | None = None
    ) -> None:
        repo, membership = await self._get(message, uow)
        membership.restore_membership(self.clock.now())
        await repo.save(membership)
        if self.permissions is not None:
            await self.permissions.grant(
                _require_uow(uow),
                membership.tenant_id,
                "tenant",
                str(membership.tenant_id),
                tenant_subject(membership.user_id),
                tenant_role_action(membership.membership_type),
            )


class PromoteMemberHandler(_MembershipMutation, CommandHandler[PromoteMember, None]):
    async def handle(
        self, message: PromoteMember, uow: UnitOfWork | None = None
    ) -> None:
        repo, membership = await self._get(message, uow)
        previous_role = membership.membership_type
        membership.promote()
        await repo.save(membership)
        if (
            self.permissions is not None
            and previous_role is not membership.membership_type
        ):
            transaction = _require_uow(uow)
            await self.permissions.remove(
                transaction,
                membership.tenant_id,
                "tenant",
                str(membership.tenant_id),
                tenant_subject(membership.user_id),
                tenant_role_action(previous_role),
            )
            await self.permissions.grant(
                transaction,
                membership.tenant_id,
                "tenant",
                str(membership.tenant_id),
                tenant_subject(membership.user_id),
                tenant_role_action(membership.membership_type),
            )


class DemoteAdminHandler(_MembershipMutation, CommandHandler[DemoteAdmin, None]):
    async def handle(self, message: DemoteAdmin, uow: UnitOfWork | None = None) -> None:
        repo, membership = await self._get(message, uow)
        admins = await repo.list_active_admins(membership.tenant_id)
        LastAdminGuard.ensure_not_last_admin(
            removing_admin=membership.active and membership.is_admin,
            active_admin_count=len(admins),
        )
        membership.demote()
        await repo.save(membership)
        if self.permissions is not None:
            transaction = _require_uow(uow)
            await self.permissions.remove(
                transaction,
                membership.tenant_id,
                "tenant",
                str(membership.tenant_id),
                tenant_subject(membership.user_id),
                tenant_role_action(TenantMembershipType.ADMIN),
            )
            await self.permissions.remove(
                transaction,
                membership.tenant_id,
                "tenant",
                str(membership.tenant_id),
                tenant_subject(membership.user_id),
                tenant_role_action(TenantMembershipType.OWNER),
            )
            await self.permissions.grant(
                transaction,
                membership.tenant_id,
                "tenant",
                str(membership.tenant_id),
                tenant_subject(membership.user_id),
                tenant_role_action(membership.membership_type),
            )


class RegisterAclHandler(CommandHandler[RegisterAcl, AclId]):
    def __init__(
        self,
        acls: RepositoryFactory[AccessControlListRepository],
        memberships: RepositoryFactory[MembershipRepository],
        ids: IdGenerator,
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.acls, self.memberships, self.ids, self.permissions = (
            acls,
            memberships,
            ids,
            permissions,
        )

    async def handle(
        self, message: RegisterAcl, uow: UnitOfWork | None = None
    ) -> AclId:
        transaction = _require_uow(uow)
        await _require_admin(
            self.memberships, transaction, message.scope.tenant_id, self.permissions
        )
        repo = self.acls(transaction)
        if await repo.get_acl(
            message.scope.tenant_id,
            message.scope.resource_type,
            message.scope.resource_id,
        ):
            raise IamDomainError("ACL already exists")
        acl = AccessControlList.register(message.scope, AclId(self.ids.new()))
        await repo.add(acl)
        return acl.id


class GrantAccessHandler(CommandHandler[GrantAccess, None]):
    def __init__(
        self,
        acls: RepositoryFactory[AccessControlListRepository],
        memberships: RepositoryFactory[MembershipRepository],
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.acls, self.memberships, self.permissions = acls, memberships, permissions

    async def handle(self, message: GrantAccess, uow: UnitOfWork | None = None) -> None:
        transaction = _require_uow(uow)
        await _require_admin(
            self.memberships, transaction, message.scope.tenant_id, self.permissions
        )
        repo = self.acls(transaction)
        acl = await repo.get_acl(
            message.scope.tenant_id,
            message.scope.resource_type,
            message.scope.resource_id,
        )
        if acl is None:
            raise IamDomainError("ACL not found")
        acl.grant(message.subject, message.action, message.effect)
        await repo.save(acl)


class RevokeAccessHandler(CommandHandler[RevokeAccess, None]):
    def __init__(
        self,
        acls: RepositoryFactory[AccessControlListRepository],
        memberships: RepositoryFactory[MembershipRepository],
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.acls, self.memberships, self.permissions = acls, memberships, permissions

    async def handle(
        self, message: RevokeAccess, uow: UnitOfWork | None = None
    ) -> None:
        transaction = _require_uow(uow)
        await _require_admin(
            self.memberships, transaction, message.scope.tenant_id, self.permissions
        )
        repo = self.acls(transaction)
        acl = await repo.get_acl(
            message.scope.tenant_id,
            message.scope.resource_type,
            message.scope.resource_id,
        )
        if acl is None:
            raise IamDomainError("ACL not found")
        acl.revoke(message.subject, message.action)
        await repo.save(acl)


class DeleteAclHandler(CommandHandler[DeleteAcl, None]):
    def __init__(
        self,
        acls: RepositoryFactory[AccessControlListRepository],
        memberships: RepositoryFactory[MembershipRepository],
        permissions: RelationshipAclSynchronizer | None = None,
    ) -> None:
        self.acls, self.memberships, self.permissions = acls, memberships, permissions

    async def handle(self, message: DeleteAcl, uow: UnitOfWork | None = None) -> None:
        transaction = _require_uow(uow)
        await _require_admin(
            self.memberships, transaction, message.scope.tenant_id, self.permissions
        )
        repo = self.acls(transaction)
        acl = await repo.get_acl(
            message.scope.tenant_id,
            message.scope.resource_type,
            message.scope.resource_id,
        )
        if acl is None:
            return
        acl.delete()
        await repo.delete(acl)


class LoginWithPasswordHandler(CommandHandler[LoginWithPassword, LoginResult]):
    def __init__(
        self,
        users: RepositoryFactory[UserRepository],
        memberships: MembershipListReadStore,
        hasher: PasswordHasher,
        clock: Clock,
    ) -> None:
        self.users, self.memberships, self.hasher, self.clock = (
            users,
            memberships,
            hasher,
            clock,
        )

    async def handle(
        self, message: LoginWithPassword, uow: UnitOfWork | None = None
    ) -> LoginResult:
        repo = self.users(_require_uow(uow))
        user = await repo.by_email(message.email)
        if (
            user is None
            or not user.can_authenticate(self.clock.now())
            or not self.hasher.verify(message.password, user.password_hash)
        ):
            raise IamDomainError("invalid credentials")
        return LoginResult(user.id, tuple(await self.memberships.list_user(user.id)))


class IssuePreAuthTokenHandler(CommandHandler[IssuePreAuthToken, IssuedToken]):
    def __init__(
        self,
        issuer: TokenIssuer,
        issuer_name: str,
        audience: str,
        ttl: timedelta,
        clock: Clock,
    ) -> None:
        self.issuer = issuer
        self.issuer_name = issuer_name
        self.audience = audience
        self.ttl = ttl
        self.clock = clock

    async def handle(
        self, message: IssuePreAuthToken, uow: UnitOfWork | None = None
    ) -> IssuedToken:
        expires = self.clock.now() + self.ttl
        return self.issuer.issue(
            TokenClaims(
                message.user_id,
                None,
                None,
                None,
                message.auth_method,
                self.issuer_name,
                self.audience,
                expires,
            )
        )


class LoginWithOidcHandler(CommandHandler[LoginResult, LoginResult]):
    def __init__(
        self,
        verifier: OidcTokenVerifier,
        users: RepositoryFactory[UserRepository],
        memberships: MembershipListReadStore,
    ) -> None:
        self.verifier, self.users, self.memberships = verifier, users, memberships

    async def handle(
        self, message: LoginWithOidc, uow: UnitOfWork | None = None
    ) -> LoginResult:
        identity = await self.verifier.verify(message.token)
        repo = self.users(_require_uow(uow))
        user = await repo.by_email(identity.email)
        if user is None or not user.active:
            raise IamDomainError("OIDC identity is not registered")
        return LoginResult(user.id, tuple(await self.memberships.list_user(user.id)))


class SelectTenantAndIssueTokensHandler(
    CommandHandler[SelectTenantAndIssueTokens, IssuedToken]
):
    def __init__(
        self,
        memberships: RepositoryFactory[MembershipRepository],
        sessions: RepositoryFactory[SessionRepository],
        issuer: TokenIssuer,
        issuer_name: str = "iam",
        audience: str = "business-api",
        ttl: timedelta = timedelta(hours=1),
        clock: Clock | None = None,
        ids: IdGenerator | None = None,
    ) -> None:
        (
            self.memberships,
            self.sessions,
            self.issuer,
            self.issuer_name,
            self.audience,
            self.ttl,
        ) = memberships, sessions, issuer, issuer_name, audience, ttl
        if clock is None or ids is None:
            raise ValueError("clock and ID generator are required")
        self.clock, self.ids = clock, ids

    async def handle(
        self, message: SelectTenantAndIssueTokens, uow: UnitOfWork | None = None
    ) -> IssuedToken:
        transaction = _require_uow(uow)
        membership = await self.memberships(transaction).find(
            message.tenant_id, message.user_id
        )
        if membership is None or not membership.active:
            raise IamDomainError("active membership required")
        expires = self.clock.now() + self.ttl
        session = Session.create(
            message.user_id, message.tenant_id, expires, SessionId(self.ids.new())
        )
        await self.sessions(transaction).add(session)
        claims = TokenClaims(
            message.user_id,
            message.tenant_id,
            membership.id,
            session.id,
            message.auth_method,
            self.issuer_name,
            self.audience,
            expires,
        )
        return self.issuer.issue(claims)


class RevokeSessionHandler(CommandHandler[RevokeSession, None]):
    def __init__(self, sessions: RepositoryFactory[SessionRepository]) -> None:
        self.sessions = sessions

    async def handle(
        self, message: RevokeSession, uow: UnitOfWork | None = None
    ) -> None:
        repo = self.sessions(_require_uow(uow))
        session = await repo.get(message.session_id)
        if session is None:
            return
        session.revoke()
        await repo.save(session)


class ListUserMembershipsHandler(
    QueryHandler[ListUserMemberships, tuple[MembershipDTO, ...]]
):
    def __init__(self, store: MembershipListReadStore) -> None:
        self.store = store

    async def handle(
        self, message: ListUserMemberships, uow: UnitOfWork | None = None
    ) -> tuple[MembershipDTO, ...]:
        return tuple(await self.store.list_user(message.user_id))


class ListTenantMembershipsHandler(
    QueryHandler[ListTenantMemberships, tuple[MembershipDTO, ...]]
):
    def __init__(self, store: MembershipListReadStore) -> None:
        self.store = store

    async def handle(
        self, message: ListTenantMemberships, uow: UnitOfWork | None = None
    ) -> tuple[MembershipDTO, ...]:
        return tuple(await self.store.list_tenant(message.tenant_id))


class SearchTenantMembershipsHandler(
    QueryHandler[SearchTenantMemberships, Page[MembershipDTO]]
):
    def __init__(self, store: MembershipListReadStore) -> None:
        self.store = store

    async def handle(
        self, message: SearchTenantMemberships, uow: UnitOfWork | None = None
    ) -> Page[MembershipDTO]:
        return await self.store.search_tenant(
            message.tenant_id, message.keyword, message.page
        )


class SearchGroupMembershipsHandler(
    QueryHandler[SearchGroupMemberships, Page[GroupMembershipDTO]]
):
    def __init__(self, store: GroupMembershipReadStore) -> None:
        self.store = store

    async def handle(
        self, message: SearchGroupMemberships, uow: UnitOfWork | None = None
    ) -> Page[GroupMembershipDTO]:
        return await self.store.search_group(
            message.group_id, message.keyword, message.page
        )


class SearchUsersHandler(QueryHandler[SearchUsers, Page[UserDTO]]):
    def __init__(self, store: DirectoryReadStore) -> None:
        self.store = store

    async def handle(
        self, message: SearchUsers, uow: UnitOfWork | None = None
    ) -> Page[UserDTO]:
        return await self.store.search_users(message.keyword, message.page)


class GetCurrentUserHandler(QueryHandler[GetCurrentUser, UserDTO | None]):
    def __init__(self, store: DirectoryReadStore) -> None:
        self.store = store

    async def handle(
        self, message: GetCurrentUser, uow: UnitOfWork | None = None
    ) -> UserDTO | None:
        return await self.store.get_user(message.user_id)


class ListAvailableTenantsHandler(QueryHandler[ListAvailableTenants, Page[TenantDTO]]):
    def __init__(self, store: DirectoryReadStore) -> None:
        self.store = store

    async def handle(
        self, message: ListAvailableTenants, uow: UnitOfWork | None = None
    ) -> Page[TenantDTO]:
        result = await self.store.list_user_tenants(
            message.user_id, message.keyword, message.page
        )
        # Directory implementations must return a page for empty results, but
        # keep the query contract total so a missing membership list is still
        # represented as a valid empty page rather than an HTTP 500.
        if result is None:
            return Page((), 0, message.page.page, message.page.size)
        return result


class SearchGroupsHandler(QueryHandler[SearchGroups, Page[GroupDTO]]):
    def __init__(self, store: DirectoryReadStore) -> None:
        self.store = store

    async def handle(
        self, message: SearchGroups, uow: UnitOfWork | None = None
    ) -> Page[GroupDTO]:
        return await self.store.search_groups(
            message.tenant_id, message.keyword, message.page
        )


class CheckAccessHandler(QueryHandler[CheckAccess, AccessDecision]):
    def __init__(
        self,
        membership: MembershipReadStore,
        store: AccessDecisionReadStore,
        evaluator: AccessDecisionEvaluator,
        groups: PrincipalGroupResolver | None = None,
    ) -> None:
        self.membership, self.store, self.evaluator, self.groups = (
            membership,
            store,
            evaluator,
            groups,
        )

    async def handle(
        self, message: CheckAccess, uow: UnitOfWork | None = None
    ) -> AccessDecision:
        active = await self.membership.is_active(message.tenant_id, message.user_id)
        subjects = {Subject(message.user_id, SubjectType.USER)}
        if self.groups is not None:
            subjects.update(
                Subject(group_id, SubjectType.GROUP)
                for group_id in await self.groups.groups_for_user(message.user_id)
            )
        # Read all entries and match against the resolved principal set. This
        # preserves direct user ACLs while allowing nested group ACLs to grant
        # access without duplicating entries for every user.
        resource = await self.store.entries(
            message.tenant_id,
            message.resource_type,
            message.resource_id,
        )
        types = await self.store.entries(message.tenant_id, message.resource_type, "*")
        # System roles are instance-scoped and therefore live under the
        # reserved tenant. Include them in role resolution for every check.
        system = await self.store.entries(SYSTEM_TENANT_ID, "system", "instance")
        return self.evaluator.evaluate(
            Subject(message.user_id),
            message.action,
            AclScope(message.tenant_id, message.resource_type, message.resource_id),
            resource,
            (*types, *system),
            active,
            subjects=subjects,
        )


class BatchCheckAccessHandler(QueryHandler[BatchCheckAccess, BatchAccessDecision]):
    def __init__(self, single: CheckAccessHandler) -> None:
        self.single = single

    async def handle(
        self, message: BatchCheckAccess, uow: UnitOfWork | None = None
    ) -> BatchAccessDecision:
        decisions: list[AccessDecision] = []
        for resource_type, resource_id, action in message.requests:
            decisions.append(
                await self.single.handle(
                    CheckAccess(
                        message.tenant_id,
                        message.user_id,
                        resource_type,
                        resource_id,
                        action,
                    ),
                    uow,
                )
            )
        return BatchAccessDecision(tuple(decisions))


class GetSessionHandler(QueryHandler[GetSession, Session | None]):
    def __init__(self, sessions: SessionReadStore) -> None:
        self.sessions = sessions

    async def handle(
        self, message: GetSession, uow: UnitOfWork | None = None
    ) -> Session | None:
        return await self.sessions.get(message.session_id)


class IsPrincipalActiveHandler(QueryHandler[IsPrincipalActive, bool]):
    def __init__(self, store: PrincipalStatusReadStore) -> None:
        self.store = store

    async def handle(
        self, message: IsPrincipalActive, uow: UnitOfWork | None = None
    ) -> bool:
        return await self.store.is_active(message.subject)


class GetAclHandler(QueryHandler[GetAcl, AccessControlList | None]):
    def __init__(self, acls: AclReadStore) -> None:
        self.acls = acls

    async def handle(
        self, message: GetAcl, uow: UnitOfWork | None = None
    ) -> AccessControlList | None:
        return await self.acls.get(message.scope)
