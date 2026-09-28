"""SQLAlchemy IAM repositories and read stores."""
# mypy: ignore-errors

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from .....kernel.application.unit_of_work import UnitOfWork
from .....kernel.application.common.page import Page, PageRequest
from .....kernel.domain.entity import EntityId
from .....kernel.infrastructure.persistence.sqlalchemy.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from ....domain.entities import (
    AccessControlList,
    ApiKey,
    ExternalSSOIdentity,
    Group,
    GroupMembership,
    Invitation,
    ServicePrincipal,
    SSOProvider,
    Membership,
    Session,
    Tenant,
    User,
)
from ....domain.value_objects import *
from ....application.dto import MembershipDTO
from ....application.ports import *
from .models import *


def _session(uow: UnitOfWork) -> AsyncSession:
    if not isinstance(uow, SqlAlchemyUnitOfWork):
        raise TypeError("IAM SQLAlchemy repositories require SqlAlchemyUnitOfWork")
    return uow.session


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, uow: UnitOfWork) -> None:
        self.session, self.uow = _session(uow), uow

    async def get(self, user_id: UserId) -> User | None:
        row = await self.session.get(UserRecord, str(user_id))
        if row is None:
            return None
        user = User.restore(
            UserId(row.id),
            row.email,
            row.password_hash,
            row.verified,
            row.version,
            row.active,
        )
        self.uow.track(user)
        return user

    async def by_email(self, email: str) -> User | None:
        row = await self.session.scalar(
            select(UserRecord).where(UserRecord.email == email.strip().lower())
        )
        if row is None:
            return None
        user = User.restore(
            UserId(row.id),
            row.email,
            row.password_hash,
            row.verified,
            row.version,
            row.active,
        )
        self.uow.track(user)
        return user

    async def add(self, user: User) -> None:
        self.session.add(
            UserRecord(
                id=str(user.id),
                email=user.email,
                password_hash=user.password_hash,
                verified=user.verified,
                active=user.active,
                version=user.version,
            )
        )
        self.uow.track(user)

    async def save(self, user: User) -> None:
        row = await self.session.get(UserRecord, str(user.id))
        if row is None:
            return await self.add(user)
        row.email, row.password_hash, row.verified, row.active, row.version = (
            user.email,
            user.password_hash,
            user.verified,
            user.active,
            user.version,
        )


class SqlAlchemyTenantRepository(TenantRepository):
    def __init__(self, uow: UnitOfWork) -> None:
        self.session, self.uow = _session(uow), uow

    async def get(self, tenant_id: TenantId) -> Tenant | None:
        row = await self.session.get(TenantRecord, str(tenant_id))
        return (
            None
            if row is None
            else Tenant.restore(TenantId(row.id), row.name, row.active, row.version)
        )

    async def add(self, tenant: Tenant) -> None:
        self.session.add(
            TenantRecord(
                id=str(tenant.id),
                name=tenant.name,
                active=tenant.active,
                version=tenant.version,
            )
        )
        await self.session.flush()
        self.uow.track(tenant)


def _membership(row: TenantMembershipRecord) -> Membership:
    return Membership.restore(
        MembershipId(row.id),
        TenantId(row.tenant_id),
        UserId(row.user_id),
        row.active,
        row.is_admin,
        row.joined_at,
        row.version,
        TenantMembershipType(row.membership_type),
    )


class SqlAlchemyGroupRepository(GroupRepository):
    def __init__(self, uow: UnitOfWork) -> None:
        self.session, self.uow = _session(uow), uow

    async def get(self, group_id: GroupId) -> Group | None:
        row = await self.session.get(GroupRecord, str(group_id))
        if row is None:
            return None
        member_rows = (
            await self.session.scalars(
                select(GroupMemberRecord).where(
                    GroupMemberRecord.group_id == row.id,
                    GroupMemberRecord.active.is_(True),
                )
            )
        ).all()
        members: frozenset[UserId | GroupId] = frozenset(
            GroupId(item.member_id)
            if item.member_type == "GROUP"
            else UserId(item.member_id)
            for item in member_rows
        )
        value = Group.restore(
            GroupId(row.id), TenantId(row.tenant_id), row.name, members, row.version
        )
        self.uow.track(value)
        return value

    async def add(self, group: Group) -> None:
        self.session.add(
            GroupRecord(
                id=str(group.id),
                tenant_id=str(group.tenant_id),
                name=group.name,
                version=group.version,
            )
        )
        await self.session.flush()
        # GroupMembershipRepository owns edge rows. Keeping edge persistence in
        # one adapter avoids inserting the same edge twice and gives removals a
        # single authoritative write path.
        self.uow.track(group)

    async def save(self, group: Group) -> None:
        row = await self.session.get(GroupRecord, str(group.id))
        if row is None:
            return await self.add(group)
        row.name, row.version = group.name, group.version
        # Membership edges are persisted by SqlAlchemyGroupMembershipRepository.


class SqlAlchemyGroupMembershipRepository(GroupMembershipRepository):
    def __init__(self, uow: UnitOfWork) -> None:
        self.session, self.uow = _session(uow), uow

    async def get(self, membership_id: GroupMembershipId) -> GroupMembership | None:
        row = await self.session.get(GroupMemberRecord, str(membership_id))
        if row is None:
            return None
        member_id: UserId | GroupId = (
            GroupId(row.member_id)
            if row.member_type == "GROUP"
            else UserId(row.member_id)
        )
        result = GroupMembership.restore(
            membership_id,
            GroupId(row.group_id),
            member_id,
            row.active,
            row.version,
            GroupMemberType(row.member_type),
        )
        self.uow.track(result)
        return result

    async def add(self, membership: GroupMembership) -> None:
        self.session.add(
            GroupMemberRecord(
                id=str(membership.id),
                group_id=str(membership.group_id),
                member_type=membership.member_type.value,
                member_id=str(membership.member_id),
            )
        )
        self.uow.track(membership)

    async def save(self, membership: GroupMembership) -> None:
        row = await self.session.get(GroupMemberRecord, str(membership.id))
        if row is not None:
            row.active = membership.active
            row.version = membership.version


class SqlAlchemyPrincipalGroupResolver(PrincipalGroupResolver):
    """Resolve direct and nested active Group principals for a user."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def groups_for_user(self, user_id: UserId) -> frozenset[GroupId]:
        async with self.session_factory() as session:
            result = await session.execute(
                text(
                    """
                WITH RECURSIVE principal_groups(group_id) AS (
                    SELECT group_id
                    FROM iam_group_members
                    WHERE member_id = :user_id
                      AND member_type IN ('USER', 'OWNER')
                      AND active = 1
                    UNION
                    SELECT memberships.group_id
                    FROM iam_group_members AS memberships
                    JOIN principal_groups AS nested
                      ON memberships.member_id = nested.group_id
                    WHERE memberships.member_type = 'GROUP'
                      AND memberships.active = 1
                )
                SELECT group_id FROM principal_groups
                """
                ),
                {"user_id": str(user_id)},
            )
            return frozenset(GroupId(row.group_id) for row in result)


class SqlAlchemySSOProviderRepository(SSOProviderRepository):
    def __init__(self, uow: UnitOfWork) -> None:
        self.session, self.uow = _session(uow), uow

    async def get(self, provider_id: SSOProviderId) -> SSOProvider | None:
        row = await self.session.get(SSOProviderRecord, str(provider_id))
        return self._provider(row)

    async def by_issuer(self, issuer: str) -> SSOProvider | None:
        row = await self.session.scalar(
            select(SSOProviderRecord).where(SSOProviderRecord.issuer == issuer)
        )
        return self._provider(row)

    def _provider(self, row: SSOProviderRecord | None) -> SSOProvider | None:
        if row is None:
            return None
        provider = SSOProvider(
            SSOProviderId(row.id),
            row.issuer,
            row.client_id,
            row.client_secret,
            active=row.active,
            is_global=row.is_global,
            version=row.version,
        )
        self.uow.track(provider)
        return provider

    async def add(self, provider: SSOProvider) -> None:
        self.session.add(
            SSOProviderRecord(
                id=str(provider.id),
                issuer=provider.issuer,
                client_id=provider.client_id,
                client_secret=provider.client_secret,
                active=provider.active,
                is_global=provider.is_global,
                version=provider.version,
            )
        )
        self.uow.track(provider)

    async def has_membership(
        self, provider_id: SSOProviderId, tenant_id: TenantId | None = None
    ) -> bool:
        query = select(SSOProviderMembershipRecord.id).where(
            SSOProviderMembershipRecord.provider_id == str(provider_id)
        )
        if tenant_id is not None:
            query = query.where(SSOProviderMembershipRecord.tenant_id == str(tenant_id))
        return await self.session.scalar(query) is not None

    async def add_membership(
        self, provider_id: SSOProviderId, tenant_id: TenantId
    ) -> None:
        from uuid import uuid4

        self.session.add(
            SSOProviderMembershipRecord(
                id=str(uuid4()), provider_id=str(provider_id), tenant_id=str(tenant_id)
            )
        )


class SqlAlchemyExternalSSOIdentityRepository(ExternalSSOIdentityRepository):
    def __init__(self, uow: UnitOfWork) -> None:
        self.session, self.uow = _session(uow), uow

    async def get_by_subject(
        self, provider_id: SSOProviderId, subject: str
    ) -> ExternalSSOIdentity | None:
        row = await self.session.scalar(
            select(ExternalSSOIdentityRecord).where(
                ExternalSSOIdentityRecord.provider_id == str(provider_id),
                ExternalSSOIdentityRecord.external_subject == subject,
            )
        )
        if row is None:
            return None
        identity = ExternalSSOIdentity(
            ExternalSSOIdentityId(row.id),
            UserId(row.user_id),
            SSOProviderId(row.provider_id),
            row.external_subject,
            version=row.version,
        )
        self.uow.track(identity)
        return identity

    async def add(self, identity: ExternalSSOIdentity) -> None:
        self.session.add(
            ExternalSSOIdentityRecord(
                id=str(identity.id),
                user_id=str(identity.user_id),
                provider_id=str(identity.provider_id),
                external_subject=identity.external_subject,
                version=identity.version,
            )
        )
        self.uow.track(identity)


class SqlAlchemyServicePrincipalRepository(ServicePrincipalRepository):
    def __init__(self, uow: UnitOfWork) -> None:
        self.session, self.uow = _session(uow), uow

    async def get(self, principal_id: ServicePrincipalId) -> ServicePrincipal | None:
        row = await self.session.get(ServicePrincipalRecord, str(principal_id))
        if row is None:
            return None
        principal = ServicePrincipal.restore(
            ServicePrincipalId(row.id),
            TenantId(row.tenant_id),
            row.name,
            active=row.active,
            version=row.version,
        )
        self.uow.track(principal)
        return principal

    async def add(self, principal: ServicePrincipal) -> None:
        self.session.add(
            ServicePrincipalRecord(
                id=str(principal.id),
                tenant_id=str(principal.tenant_id),
                name=principal.name,
                active=principal.active,
                version=principal.version,
            )
        )
        self.uow.track(principal)

    async def save(self, principal: ServicePrincipal) -> None:
        row = await self.session.get(ServicePrincipalRecord, str(principal.id))
        if row is None:
            await self.add(principal)
            return
        row.name, row.active, row.version = (
            principal.name,
            principal.active,
            principal.version,
        )


class SqlAlchemyApiKeyRepository(ApiKeyRepository):
    def __init__(self, uow: UnitOfWork) -> None:
        self.session, self.uow = _session(uow), uow

    async def get(self, api_key_id: ApiKeyId) -> ApiKey | None:
        row = await self.session.get(ApiKeyRecord, str(api_key_id))
        if row is None:
            return None
        key = ApiKey(
            ApiKeyId(row.id),
            ServicePrincipalId(row.principal_id),
            row.secret_hash,
            revoked=row.revoked,
            version=row.version,
        )
        self.uow.track(key)
        return key

    async def add(self, api_key: ApiKey) -> None:
        self.session.add(
            ApiKeyRecord(
                id=str(api_key.id),
                principal_id=str(api_key.principal_id),
                secret_hash=api_key.secret_hash,
                revoked=api_key.revoked,
                version=api_key.version,
            )
        )
        self.uow.track(api_key)

    async def save(self, api_key: ApiKey) -> None:
        row = await self.session.get(ApiKeyRecord, str(api_key.id))
        if row is None:
            return await self.add(api_key)
        row.revoked, row.version = api_key.revoked, api_key.version


class SqlAlchemyGroupGraph(GroupGraph):
    """Read-only group graph used by the domain cycle guard."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def groups(self) -> dict[GroupId, frozenset[GroupId]]:
        async with self.session_factory() as session:
            rows = (
                await session.scalars(
                    select(GroupMemberRecord).where(
                        GroupMemberRecord.member_type == "GROUP"
                    )
                )
            ).all()
            graph: dict[GroupId, set[GroupId]] = {}
            for row in rows:
                graph.setdefault(GroupId(row.group_id), set()).add(
                    GroupId(row.member_id)
                )
            return {key: frozenset(value) for key, value in graph.items()}


class SqlAlchemyMembershipRepository(MembershipRepository):
    def __init__(self, uow: UnitOfWork) -> None:
        self.session, self.uow = _session(uow), uow

    async def get(self, membership_id: MembershipId) -> Membership | None:
        row = await self.session.get(TenantMembershipRecord, str(membership_id))
        if row is None:
            return None
        value = _membership(row)
        self.uow.track(value)
        return value

    async def find(self, tenant_id: TenantId, user_id: UserId) -> Membership | None:
        row = await self.session.scalar(
            select(TenantMembershipRecord).where(
                TenantMembershipRecord.tenant_id == str(tenant_id),
                TenantMembershipRecord.user_id == str(user_id),
            )
        )
        if row is None:
            return None
        value = _membership(row)
        self.uow.track(value)
        return value

    async def list_user(self, user_id: UserId) -> list[Membership]:
        rows = (
            await self.session.scalars(
                select(TenantMembershipRecord).where(
                    TenantMembershipRecord.user_id == str(user_id)
                )
            )
        ).all()
        return [_membership(row) for row in rows]

    async def list_active_admins(self, tenant_id: TenantId) -> list[Membership]:
        rows = (
            await self.session.scalars(
                select(TenantMembershipRecord).where(
                    TenantMembershipRecord.tenant_id == str(tenant_id),
                    TenantMembershipRecord.active.is_(True),
                    TenantMembershipRecord.is_admin.is_(True),
                )
            )
        ).all()
        return [_membership(row) for row in rows]

    async def add(self, membership: Membership) -> None:
        self.session.add(
            TenantMembershipRecord(
                id=str(membership.id),
                tenant_id=str(membership.tenant_id),
                user_id=str(membership.user_id),
                active=membership.active,
                is_admin=membership.is_admin,
                membership_type=membership.membership_type.value,
                joined_at=membership.joined_at,
                version=membership.version,
            )
        )
        self.uow.track(membership)

    async def save(self, membership: Membership) -> None:
        row = await self.session.get(TenantMembershipRecord, str(membership.id))
        if row is None:
            return await self.add(membership)
        row.active, row.is_admin, row.membership_type, row.joined_at, row.version = (
            membership.active,
            membership.is_admin,
            membership.membership_type.value,
            membership.joined_at,
            membership.version,
        )


def _acl(row: AclRecord, entries: list[AclEntryRecord]) -> AccessControlList:
    return AccessControlList.restore(
        AclId(row.id),
        AclScope(TenantId(row.tenant_id), row.resource_type, row.resource_id),
        tuple(
            AccessControlEntry(
                Subject(
                    _subject_id(entry.subject_type, entry.subject_id),
                    SubjectType(entry.subject_type),
                ),
                parse_acl_permission(entry.action),
                Effect(entry.effect),
            )
            for entry in entries
        ),
        row.version,
    )


def _subject_id(subject_type: str, value: str) -> EntityId[UUID]:
    ids = {
        SubjectType.USER: UserId,
        SubjectType.GROUP: GroupId,
        SubjectType.SERVICE_PRINCIPAL: ServicePrincipalId,
        SubjectType.API_KEY: ApiKeyId,
    }
    return ids[SubjectType(subject_type)](value)


class SqlAlchemyAccessControlListRepository(AccessControlListRepository):
    def __init__(self, uow: UnitOfWork) -> None:
        self.session, self.uow = _session(uow), uow

    async def get_acl(
        self, tenant_id: TenantId, resource_type: str, resource_id: str
    ) -> AccessControlList | None:
        row = await self.session.scalar(
            select(AclRecord).where(
                AclRecord.tenant_id == str(tenant_id),
                AclRecord.resource_type == resource_type,
                AclRecord.resource_id == resource_id,
            )
        )
        if row is None:
            return None
        entries = (
            await self.session.scalars(
                select(AclEntryRecord).where(AclEntryRecord.acl_id == row.id)
            )
        ).all()
        value = _acl(row, list(entries))
        self.uow.track(value)
        return value

    async def list_type_acl(
        self, tenant_id: TenantId, resource_type: str
    ) -> list[AccessControlList]:
        rows = (
            await self.session.scalars(
                select(AclRecord).where(
                    AclRecord.tenant_id == str(tenant_id),
                    AclRecord.resource_type == resource_type,
                    AclRecord.resource_id == "*",
                )
            )
        ).all()
        result: list[AccessControlList] = []
        for row in rows:
            entries = (
                await self.session.scalars(
                    select(AclEntryRecord).where(AclEntryRecord.acl_id == row.id)
                )
            ).all()
            result.append(_acl(row, list(entries)))
        return result

    async def add(self, acl: AccessControlList) -> None:
        self.session.add(
            AclRecord(
                id=str(acl.id),
                tenant_id=str(acl.scope.tenant_id),
                resource_type=acl.scope.resource_type,
                resource_id=acl.scope.resource_id,
                version=acl.version,
            )
        )
        # AclEntryRecord has a foreign key to iam_acls, but the SQLAlchemy
        # models intentionally do not define a relationship between the two
        # records. Flush the parent explicitly so SQLite never attempts to
        # insert an entry before its ACL row exists.
        await self.session.flush()
        for entry in acl.entries.values():
            self.session.add(
                AclEntryRecord(
                    acl_id=str(acl.id),
                    subject_type=entry.subject.subject_type.value,
                    subject_id=str(entry.subject.subject_id),
                    action=entry.action.value,
                    effect=entry.effect.value,
                )
            )
        self.uow.track(acl)

    async def save(self, acl: AccessControlList) -> None:
        row = await self.session.get(AclRecord, str(acl.id))
        if row is None:
            return await self.add(acl)
        row.version = acl.version
        await self.session.execute(
            delete(AclEntryRecord).where(AclEntryRecord.acl_id == str(acl.id))
        )
        for entry in acl.entries.values():
            self.session.add(
                AclEntryRecord(
                    acl_id=str(acl.id),
                    subject_type=entry.subject.subject_type.value,
                    subject_id=str(entry.subject.subject_id),
                    action=entry.action.value,
                    effect=entry.effect.value,
                )
            )

    async def delete(self, acl: AccessControlList) -> None:
        await self.session.execute(
            delete(AclEntryRecord).where(AclEntryRecord.acl_id == str(acl.id))
        )
        await self.session.execute(delete(AclRecord).where(AclRecord.id == str(acl.id)))


class SqlAlchemyMembershipReadStore(MembershipReadStore, MembershipListReadStore):
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def is_active(self, tenant_id: TenantId, user_id: UserId) -> bool:
        async with self.session_factory() as session:
            return bool(
                await session.scalar(
                    select(TenantMembershipRecord.id).where(
                        TenantMembershipRecord.tenant_id == str(tenant_id),
                        TenantMembershipRecord.user_id == str(user_id),
                        TenantMembershipRecord.active.is_(True),
                    )
                )
            )

    async def list_user(self, user_id: UserId) -> list[MembershipDTO]:
        async with self.session_factory() as session:
            rows = (
                await session.scalars(
                    select(TenantMembershipRecord).where(
                        TenantMembershipRecord.user_id == str(user_id)
                    )
                )
            ).all()
            return [
                MembershipDTO(
                    MembershipId(row.id),
                    TenantId(row.tenant_id),
                    UserId(row.user_id),
                    row.active,
                    row.is_admin,
                    membership_type=TenantMembershipType(row.membership_type),
                )
                for row in rows
            ]

    async def list_tenant(self, tenant_id: TenantId) -> list[MembershipDTO]:
        async with self.session_factory() as session:
            rows = (
                await session.scalars(
                    select(TenantMembershipRecord).where(
                        TenantMembershipRecord.tenant_id == str(tenant_id)
                    )
                )
            ).all()
            return [
                MembershipDTO(
                    MembershipId(row.id),
                    TenantId(row.tenant_id),
                    UserId(row.user_id),
                    row.active,
                    row.is_admin,
                    membership_type=TenantMembershipType(row.membership_type),
                )
                for row in rows
            ]

    async def search_tenant(
        self, tenant_id: TenantId, keyword: str, page: PageRequest
    ) -> Page[MembershipDTO]:
        async with self.session_factory() as session:
            query = (
                select(TenantMembershipRecord, UserRecord.email)
                .join(UserRecord, UserRecord.id == TenantMembershipRecord.user_id)
                .where(TenantMembershipRecord.tenant_id == str(tenant_id))
            )
            if keyword.strip():
                pattern = f"%{keyword.strip()}%"
                query = query.where(
                    or_(
                        UserRecord.email.ilike(pattern),
                        TenantMembershipRecord.user_id.ilike(pattern),
                    )
                )
            total = int(
                await session.scalar(
                    select(func.count()).select_from(query.order_by(None).subquery())
                )
                or 0
            )
            rows = (
                await session.execute(
                    query.order_by(UserRecord.email, TenantMembershipRecord.id)
                    .offset(page.offset)
                    .limit(page.limit)
                )
            ).all()
            return Page(
                tuple(
                    MembershipDTO(
                        MembershipId(row.id),
                        TenantId(row.tenant_id),
                        UserId(row.user_id),
                        row.active,
                        row.is_admin,
                        email,
                        TenantMembershipType(row.membership_type),
                    )
                    for row, email in rows
                ),
                total,
                page.page,
                page.size,
            )


class SqlAlchemyGroupMembershipReadStore(GroupMembershipReadStore):
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def search_group(
        self, group_id: GroupId, keyword: str, page: PageRequest
    ) -> Page[GroupMembershipDTO]:
        async with self.session_factory() as session:
            nested_group = aliased(GroupRecord)
            query = (
                select(GroupMemberRecord, UserRecord.email, nested_group.name)
                .outerjoin(
                    UserRecord,
                    and_(
                        GroupMemberRecord.member_type.in_(("USER", "OWNER")),
                        UserRecord.id == GroupMemberRecord.member_id,
                    ),
                )
                .outerjoin(
                    nested_group,
                    and_(
                        GroupMemberRecord.member_type == "GROUP",
                        nested_group.id == GroupMemberRecord.member_id,
                    ),
                )
                .where(GroupMemberRecord.group_id == str(group_id))
            )
            if keyword.strip():
                pattern = f"%{keyword.strip()}%"
                query = query.where(
                    or_(
                        UserRecord.email.ilike(pattern),
                        nested_group.name.ilike(pattern),
                        GroupMemberRecord.member_id.ilike(pattern),
                    )
                )
            total = int(
                await session.scalar(
                    select(func.count()).select_from(query.order_by(None).subquery())
                )
                or 0
            )
            rows = (
                await session.execute(
                    query.order_by(GroupMemberRecord.member_type, GroupMemberRecord.id)
                    .offset(page.offset)
                    .limit(page.limit)
                )
            ).all()
            return Page(
                tuple(
                    GroupMembershipDTO(
                        GroupMembershipId(row.id),
                        GroupId(row.group_id),
                        GroupId(row.member_id)
                        if row.member_type == "GROUP"
                        else UserId(row.member_id),
                        GroupMemberType(row.member_type),
                        row.active,
                        email or group_name,
                    )
                    for row, email, group_name in rows
                ),
                total,
                page.page,
                page.size,
            )


class SqlAlchemyDirectoryReadStore(DirectoryReadStore):
    """Read-only directory queries used by selectors and autocomplete views."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _pattern(keyword: str) -> str:
        return f"%{keyword.strip()}%"

    async def search_users(self, keyword: str, page: PageRequest) -> Page[UserDTO]:
        async with self.session_factory() as session:
            query = select(UserRecord)
            if keyword.strip():
                query = query.where(UserRecord.email.ilike(self._pattern(keyword)))
            total = int(
                await session.scalar(select(func.count()).select_from(query.subquery()))
                or 0
            )
            rows = (
                await session.scalars(
                    query.order_by(UserRecord.email, UserRecord.id)
                    .offset(page.offset)
                    .limit(page.limit)
                )
            ).all()
            return Page(
                tuple(UserDTO(UserId(row.id), row.email, row.active) for row in rows),
                total,
                page.page,
                page.size,
            )

    async def get_user(self, user_id: UserId) -> UserDTO | None:
        async with self.session_factory() as session:
            row = await session.get(UserRecord, str(user_id))
            if row is None:
                return None
            return UserDTO(UserId(row.id), row.email, row.active)

    async def list_user_tenants(
        self, user_id: UserId, keyword: str, page: PageRequest
    ) -> Page[TenantDTO]:
        async with self.session_factory() as session:
            query = (
                select(TenantRecord)
                .join(
                    TenantMembershipRecord,
                    TenantMembershipRecord.tenant_id == TenantRecord.id,
                )
                .where(
                    TenantMembershipRecord.user_id == str(user_id),
                    TenantMembershipRecord.active.is_(True),
                )
            )
            if keyword.strip():
                query = query.where(TenantRecord.name.ilike(self._pattern(keyword)))
            query = query.order_by(TenantRecord.name, TenantRecord.id)
            total = int(
                await session.scalar(
                    select(func.count()).select_from(query.order_by(None).subquery())
                )
                or 0
            )
            rows = (
                await session.scalars(query.offset(page.offset).limit(page.limit))
            ).all()
            return Page(
                tuple(TenantDTO(TenantId(row.id), row.name) for row in rows),
                total,
                page.page,
                page.size,
            )

    async def search_groups(
        self, tenant_id: TenantId, keyword: str, page: PageRequest
    ) -> Page[GroupDTO]:
        async with self.session_factory() as session:
            query = select(GroupRecord).where(GroupRecord.tenant_id == str(tenant_id))
            if keyword.strip():
                query = query.where(GroupRecord.name.ilike(self._pattern(keyword)))
            total = int(
                await session.scalar(select(func.count()).select_from(query.subquery()))
                or 0
            )
            rows = (
                await session.scalars(
                    query.order_by(GroupRecord.name, GroupRecord.id)
                    .offset(page.offset)
                    .limit(page.limit)
                )
            ).all()
            return Page(
                tuple(
                    GroupDTO(GroupId(row.id), TenantId(row.tenant_id), row.name)
                    for row in rows
                ),
                total,
                page.page,
                page.size,
            )


class SqlAlchemyPrincipalStatusReadStore(PrincipalStatusReadStore):
    """Lifecycle read model backed by the polymorphic principal root."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def is_active(self, subject: Subject) -> bool:
        if subject.subject_type not in {
            SubjectType.USER,
            SubjectType.SERVICE_PRINCIPAL,
        }:
            return False
        async with self.session_factory() as session:
            active = await session.scalar(
                select(PrincipalRecord.active).where(
                    PrincipalRecord.id == str(subject.subject_id),
                    PrincipalRecord.principal_type == subject.subject_type.value,
                )
            )
            return bool(active)


class SqlAlchemySessionRepository(SessionRepository):
    def __init__(self, uow: UnitOfWork) -> None:
        self.session, self.uow = _session(uow), uow

    async def get(self, session_id: SessionId) -> Session | None:
        row = await self.session.get(SessionRecord, str(session_id))
        if row is None:
            return None
        value = Session.restore(
            SessionId(row.id),
            UserId(row.user_id),
            TenantId(row.tenant_id),
            row.expires_at,
            row.revoked,
            row.version,
        )
        self.uow.track(value)
        return value

    async def add(self, session: Session) -> None:
        self.session.add(
            SessionRecord(
                id=str(session.id),
                user_id=str(session.user_id),
                tenant_id=str(session.tenant_id),
                expires_at=session.expires_at,
                revoked=session.revoked,
                version=session.version,
            )
        )
        self.uow.track(session)

    async def save(self, session: Session) -> None:
        row = await self.session.get(SessionRecord, str(session.id))
        if row is None:
            return await self.add(session)
        row.revoked, row.version = session.revoked, session.version


class SqlAlchemyInvitationRepository(InvitationRepository):
    def __init__(self, uow: UnitOfWork) -> None:
        self.session, self.uow = _session(uow), uow

    async def get(self, invitation_id: InvitationId) -> Invitation | None:
        row = await self.session.get(InvitationRecord, str(invitation_id))
        if row is None:
            return None
        value = Invitation.restore(
            InvitationId(row.id),
            TenantId(row.tenant_id),
            UserId(row.user_id),
            row.token_hash,
            row.expires_at,
            row.accepted,
            row.revoked,
            row.version,
        )
        self.uow.track(value)
        return value

    async def add(self, invitation: Invitation) -> None:
        self.session.add(
            InvitationRecord(
                id=str(invitation.id),
                tenant_id=str(invitation.tenant_id),
                user_id=str(invitation.user_id),
                token_hash=invitation.token_hash,
                expires_at=invitation.expires_at,
                accepted=invitation.accepted,
                revoked=invitation.revoked,
                version=invitation.version,
            )
        )
        self.uow.track(invitation)

    async def save(self, invitation: Invitation) -> None:
        row = await self.session.get(InvitationRecord, str(invitation.id))
        if row is None:
            return await self.add(invitation)
        row.accepted, row.revoked, row.version = (
            invitation.accepted,
            invitation.revoked,
            invitation.version,
        )


class SqlAlchemyAccessDecisionReadStore(AccessDecisionReadStore):
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def entries(
        self,
        tenant_id: TenantId,
        resource_type: str,
        resource_id: str,
        subject_id: UserId | None = None,
    ) -> list[AccessControlEntry]:
        async with self.session_factory() as session:
            query = select(AclDecisionRecord).where(
                AclDecisionRecord.tenant_id == str(tenant_id),
                AclDecisionRecord.resource_type == resource_type,
                AclDecisionRecord.resource_id == resource_id,
            )
            if subject_id is not None:
                query = query.where(AclDecisionRecord.subject_id == str(subject_id))
            rows = (await session.scalars(query)).all()
            return [
                AccessControlEntry(
                    Subject(
                        _subject_id(row.subject_type, row.subject_id),
                        SubjectType(row.subject_type),
                    ),
                    parse_acl_permission(row.action),
                    Effect(row.effect),
                )
                for row in rows
            ]


class SqlAlchemySessionReadStore(SessionReadStore):
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def get(self, session_id: SessionId) -> Session | None:
        async with self.session_factory() as session:
            row = await session.get(SessionRecord, str(session_id))
            if row is None:
                return None
            return Session.restore(
                SessionId(row.id),
                UserId(row.user_id),
                TenantId(row.tenant_id),
                row.expires_at,
                row.revoked,
                row.version,
            )


class SqlAlchemyAclReadStore(AclReadStore):
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def get(self, scope: AclScope) -> AccessControlList | None:
        async with self.session_factory() as session:
            row = await session.scalar(
                select(AclRecord).where(
                    AclRecord.tenant_id == str(scope.tenant_id),
                    AclRecord.resource_type == scope.resource_type,
                    AclRecord.resource_id == scope.resource_id,
                )
            )
            if row is None:
                return None
            entries = (
                await session.scalars(
                    select(AclEntryRecord).where(AclEntryRecord.acl_id == row.id)
                )
            ).all()
            return _acl(row, list(entries))
