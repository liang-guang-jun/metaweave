"""Synchronize relationship roles with the tenant-scoped ACL store."""

from __future__ import annotations

from ...kernel.application.unit_of_work import UnitOfWork
from ..domain.entities import AccessControlList
from ..domain.value_objects import (
    AclId,
    AclScope,
    Action,
    IAMRole,
    Effect,
    Subject,
    SubjectType,
    TenantId,
    TenantMembershipType,
    GroupId,
    GroupMemberType,
    SystemAdminRole,
    SYSTEM_TENANT_ID,
    UserId,
    action_for_role,
)
from .ports import (
    AccessControlListRepository,
    IdGenerator,
    PrincipalGroupResolver,
    RepositoryFactory,
)


class RelationshipAclSynchronizer:
    """Persist role-derived ACL entries in the same command transaction."""

    def __init__(
        self,
        acls: RepositoryFactory[AccessControlListRepository],
        ids: IdGenerator,
        groups: PrincipalGroupResolver | None = None,
    ) -> None:
        self.acls = acls
        self.ids = ids
        self.groups = groups

    async def grant(
        self,
        uow: UnitOfWork,
        tenant_id: TenantId,
        resource_type: str,
        resource_id: str,
        subject: Subject,
        action: Action | IAMRole,
    ) -> None:
        repo = self.acls(uow)
        scope = AclScope(tenant_id, resource_type, resource_id)
        acl = await repo.get_acl(tenant_id, resource_type, resource_id)
        if acl is None:
            acl = AccessControlList.register(scope, AclId(self.ids.new()))
            acl.grant(subject, action, Effect.ALLOW)
            await repo.add(acl)
            return
        existing = acl.entries.get((subject, action))
        # An explicit DENY is an intentional override and must not be replaced
        # by a relationship re-sync.
        if existing is not None and existing.effect is Effect.DENY:
            return
        acl.grant(subject, action, Effect.ALLOW)
        await repo.save(acl)

    async def remove(
        self,
        uow: UnitOfWork,
        tenant_id: TenantId,
        resource_type: str,
        resource_id: str,
        subject: Subject,
        action: Action | IAMRole,
    ) -> None:
        repo = self.acls(uow)
        acl = await repo.get_acl(tenant_id, resource_type, resource_id)
        if acl is None:
            return
        existing = acl.entries.get((subject, action))
        if existing is None or existing.effect is Effect.DENY:
            return
        acl.remove(subject, action)
        if not acl.entries:
            acl.delete()
            await repo.delete(acl)
        else:
            await repo.save(acl)

    async def grant_system_role(
        self, uow: UnitOfWork, subject: Subject, role: SystemAdminRole
    ) -> None:
        await self.grant(
            uow,
            SYSTEM_TENANT_ID,
            "system",
            "instance",
            subject,
            system_role_action(role),
        )

    async def remove_system_role(
        self, uow: UnitOfWork, subject: Subject, role: SystemAdminRole
    ) -> None:
        await self.remove(
            uow,
            SYSTEM_TENANT_ID,
            "system",
            "instance",
            subject,
            system_role_action(role),
        )

    async def has_tenant_admin_access(
        self, uow: UnitOfWork, tenant_id: TenantId, user_id: UserId
    ) -> bool:
        """Check the tenant administrator relationship from the ACL itself."""
        acl = await self.acls(uow).get_acl(tenant_id, "tenant", str(tenant_id))
        if acl is None:
            return False
        subject = tenant_subject(user_id)
        return any(
            entry.subject == subject
            and entry.effect is Effect.ALLOW
            and entry.action
            in {
                tenant_role_action(TenantMembershipType.ADMIN),
                tenant_role_action(TenantMembershipType.OWNER),
            }
            for entry in acl.entries.values()
        )

    async def has_system_admin_access(self, uow: UnitOfWork, user_id: UserId) -> bool:
        """Check the instance administrator relationship from the system ACL."""
        acl = await self.acls(uow).get_acl(SYSTEM_TENANT_ID, "system", "instance")
        if acl is None:
            return False
        subjects = await self._subjects_for(user_id)
        action = system_role_action(SystemAdminRole.SUPER_ADMIN)
        return any(
            entry.subject in subjects
            and entry.action == action
            and entry.effect is Effect.ALLOW
            for entry in acl.entries.values()
        )

    async def has_any_system_admin(self, uow: UnitOfWork) -> bool:
        """Return whether the instance ACL contains an active admin grant."""
        acl = await self.acls(uow).get_acl(SYSTEM_TENANT_ID, "system", "instance")
        if acl is None:
            return False
        action = system_role_action(SystemAdminRole.SUPER_ADMIN)
        return any(
            entry.action == action and entry.effect is Effect.ALLOW
            for entry in acl.entries.values()
        )

    async def _subjects_for(self, user_id: UserId) -> frozenset[Subject]:
        subjects = {tenant_subject(user_id)}
        if self.groups is not None:
            subjects.update(
                group_subject(group_id)
                for group_id in await self.groups.groups_for_user(user_id)
            )
        return frozenset(subjects)


def tenant_role_action(role: TenantMembershipType) -> IAMRole:
    return action_for_role(role)


def group_role_action(role: GroupMemberType) -> IAMRole:
    return action_for_role(role)


def system_role_action(role: SystemAdminRole) -> IAMRole:
    return action_for_role(role)


def tenant_subject(user_id: UserId) -> Subject:
    return Subject(user_id, SubjectType.USER)


def group_subject(member_id: UserId | GroupId) -> Subject:
    return Subject(
        member_id,
        SubjectType.GROUP if isinstance(member_id, GroupId) else SubjectType.USER,
    )
