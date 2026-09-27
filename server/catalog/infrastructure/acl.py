from __future__ import annotations

# ruff: noqa
# mypy: ignore-errors

from collections.abc import Sequence

from ...iam.application.ports import AccessControlListRepository
from ...iam.domain.services import AccessDecision
from ...iam.domain.value_objects import AccessControlEntry, Action, AclScope, Effect, Subject, TenantId, parse_acl_permission
from ...kernel.application.unit_of_work import UnitOfWork
from ..application.dto import PermissionSourceDTO
from ...iam.application.ports import RepositoryFactory
from ..application.ports import CatalogAclAuthorizationService
from server.iam.infrastructure.persistence.sqlalchemy.models import AclEntryRecord, AclRecord
from sqlalchemy import select


class IamCatalogAclAuthorizationService(CatalogAclAuthorizationService):
    """Catalog adapter over the IAM ACL repository and evaluator primitives."""

    def __init__(self, acls: RepositoryFactory[AccessControlListRepository], session_factory=None) -> None:
        self.acls = acls
        self.session_factory = session_factory

    async def _entries(self, scope: AclScope, uow: UnitOfWork) -> tuple[AccessControlEntry, ...]:
        acl = await self.acls(uow).get_acl(scope.tenant_id, scope.resource_type, scope.resource_id)
        return tuple(acl.entries.values()) if acl else ()

    async def _read_entries(self, scope: AclScope) -> tuple[AccessControlEntry, ...]:
        if self.session_factory is None:
            return ()
        async with self.session_factory() as session:
            acl = await session.scalar(
                select(AclRecord).where(
                    AclRecord.tenant_id == str(scope.tenant_id),
                    AclRecord.resource_type == scope.resource_type,
                    AclRecord.resource_id == scope.resource_id,
                )
            )
            if acl is None:
                return ()
            rows = (
                await session.scalars(
                    select(AclEntryRecord).where(AclEntryRecord.acl_id == acl.id)
                )
            ).all()
            from server.iam.infrastructure.persistence.sqlalchemy.repositories import _subject_id
            from server.iam.domain.value_objects import SubjectType
            return tuple(
                AccessControlEntry(
                    Subject(_subject_id(row.subject_type, row.subject_id), SubjectType(row.subject_type)),
                    parse_acl_permission(row.action),
                    Effect(row.effect),
                )
                for row in rows
            )

    async def check(self, *, subject: Subject, tenant_id: TenantId, action: Action, scopes: Sequence[AclScope], uow: UnitOfWork | None) -> AccessDecision:
        for scope in scopes:
            source = await self._entries(scope, uow) if uow is not None else await self._read_entries(scope)
            entries = [entry for entry in source if entry.subject == subject and entry.action == action]
            if entries:
                entry = next((item for item in entries if item.effect is Effect.DENY), entries[0])
                return AccessDecision(entry.effect is Effect.ALLOW, entry.effect.value.lower(), scope)
        return AccessDecision(False, "no_matching_rule")

    async def list_permissions(self, *, tenant_id: TenantId, scopes: Sequence[AclScope], uow: UnitOfWork | None) -> tuple[PermissionSourceDTO, ...]:
        result: list[PermissionSourceDTO] = []
        for index, scope in enumerate(scopes):
            entries = await self._entries(scope, uow) if uow is not None else await self._read_entries(scope)
            for entry in entries:
                result.append(PermissionSourceDTO(entry.subject, entry.action, entry.effect, scope.resource_type, scope.resource_id, index > 0))
        return tuple(result)

    async def grant(self, *, tenant_id: TenantId, resource_type: str, resource_id: str, subject: Subject, action: Action, effect: Effect, uow: UnitOfWork) -> None:
        acl = self.acls(uow)
        value = await acl.get_acl(tenant_id, resource_type, resource_id)
        from server.iam.domain.entities import AccessControlList
        from server.iam.domain.value_objects import AclId
        if value is None:
            value = AccessControlList.register(AclScope(tenant_id, resource_type, resource_id), AclId(__import__("uuid").uuid4()))
            value.grant(subject, action, effect)
            await acl.add(value)
        else:
            value.grant(subject, action, effect)
            await acl.save(value)

    async def revoke(self, *, tenant_id: TenantId, resource_type: str, resource_id: str, subject: Subject, action: Action, uow: UnitOfWork) -> None:
        value = await self.acls(uow).get_acl(tenant_id, resource_type, resource_id)
        if value is None:
            return
        value.revoke(subject, action)
        await self.acls(uow).save(value)
