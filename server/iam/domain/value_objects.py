"""IAM identities and immutable value objects."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from ...kernel.domain.entity import EntityId


# todo: 这里不指回kernel的UID嘛?
class _UuidId(EntityId[UUID]):
    def __init__(self, value: UUID | str) -> None:
        self._value = UUID(value) if isinstance(value, str) else value

    @property
    def value(self) -> UUID:
        return self._value

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._value!s})"


class UserId(_UuidId):
    """User identity."""


class TenantId(_UuidId):
    """Tenant identity."""


# Reserved scope used only for instance-level system role ACLs.
SYSTEM_TENANT_ID = TenantId(UUID(int=0))


class MembershipId(_UuidId):
    """Membership identity."""


class InvitationId(_UuidId):
    """Invitation identity."""


class SessionId(_UuidId):
    """Session identity."""


class AclId(_UuidId):
    """ACL identity."""


class GroupId(_UuidId):
    """Tenant-local group identity."""


class GroupMembershipId(_UuidId):
    """Identity of a user/group membership in a group."""


class ExternalSSOIdentityId(_UuidId):
    """External identity link identity."""


class SSOProviderId(_UuidId):
    """SSO provider configuration identity."""


class ServicePrincipalId(_UuidId):
    """Non-human workload identity."""


class ApiKeyId(_UuidId):
    """Revocable API-key identity."""


class SubjectType(StrEnum):
    """Supported ACL subject types."""

    USER = "USER"
    GROUP = "GROUP"
    SERVICE_PRINCIPAL = "SERVICE_PRINCIPAL"
    API_KEY = "API_KEY"


class GroupMemberType(StrEnum):
    """Role of an entry in a group's membership edge table."""

    USER = "USER"
    GROUP = "GROUP"
    OWNER = "OWNER"


class SystemAdminRole(StrEnum):
    """Instance-level system roles."""

    SUPER_ADMIN = "SUPER_ADMIN"


class TenantMembershipType(StrEnum):
    """Role carried by a user membership in a tenant."""

    MEMBER = "MEMBER"
    ADMIN = "ADMIN"
    OWNER = "OWNER"


class Effect(StrEnum):
    """ACL decision effect."""

    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass(frozen=True, slots=True)
class Subject:
    """A principal referenced by an ACL."""

    subject_id: EntityId[UUID]
    subject_type: SubjectType = SubjectType.USER

    def __post_init__(self) -> None:
        expected = {
            SubjectType.USER: UserId,
            SubjectType.GROUP: GroupId,
            SubjectType.SERVICE_PRINCIPAL: ServicePrincipalId,
            SubjectType.API_KEY: ApiKeyId,
        }[self.subject_type]
        if not isinstance(self.subject_id, expected):
            raise ValueError(f"{self.subject_type} requires {expected.__name__}")


@dataclass(frozen=True, slots=True)
class ResourceRef:
    """External resource reference."""

    resource_type: str
    resource_id: str

    def __post_init__(self) -> None:
        if not self.resource_type.strip() or not self.resource_id.strip():
            raise ValueError("resource_type and resource_id are required")


@dataclass(frozen=True, slots=True)
class AclScope:
    """Tenant-scoped ACL identity."""

    tenant_id: TenantId
    resource_type: str
    resource_id: str

    @property
    def resource(self) -> ResourceRef:
        return ResourceRef(self.resource_type, self.resource_id)

    def __post_init__(self) -> None:
        if not self.resource_type.strip() or not self.resource_id.strip():
            raise ValueError("ACL resource fields are required")


class Action(StrEnum):
    """Independent operation performed against a resource."""

    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MANAGE = "manage"

    @classmethod
    def _missing_(cls, value: object) -> Action | None:
        """Read legacy persisted/catalog action values without reintroducing them."""
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        legacy = {
            "read": cls.READ,
            "create": cls.CREATE,
            "update": cls.UPDATE,
            "write": cls.UPDATE,
            "delete": cls.DELETE,
            "manage": cls.MANAGE,
            "catalog.read": cls.READ,
            "catalog.write": cls.UPDATE,
            "catalog.delete": cls.DELETE,
        }
        return legacy.get(normalized)


class IAMRole(StrEnum):
    """Stable IAM relationship values persisted in ACL records."""

    SYSTEM_SUPER_ADMIN = "system.super_admin"
    TENANT_MEMBER = "tenant.member"
    TENANT_ADMIN = "tenant.admin"
    TENANT_OWNER = "tenant.owner"
    GROUP_USER_MEMBER = "group.user_member"
    GROUP_GROUP_MEMBER = "group.group_member"
    GROUP_OWNER = "group.owner"


# Backward-compatible import for integrations that used the old name.
# Deprecated: use IAMRole for identity relationships.
RoleAction = IAMRole


class ResourceType(StrEnum):
    SYSTEM = "system"
    TENANT = "tenant"
    GROUP = "group"
    WORKSPACE = "workspace"
    NODE = "node"


# Resource operations are intentionally kept separate from IAM relationship
# values. Add resource types/roles here without creating compound action
# strings such as ``mapping.update``.
_ALL_ACTIONS = frozenset(Action)
_TENANT_READ = frozenset({Action.READ})
_TENANT_MANAGE = _ALL_ACTIONS

# Flat cross-product matrix: each key is an independent resource/role pair.
# Adding a resource or relationship never requires creating compound action
# strings such as ``mapping.update``.
ACL_POLICY_MATRIX: dict[tuple[ResourceType, IAMRole], frozenset[Action]] = {
    (ResourceType.TENANT, IAMRole.TENANT_MEMBER): _TENANT_READ,
    (ResourceType.TENANT, IAMRole.TENANT_ADMIN): _TENANT_MANAGE,
    (ResourceType.TENANT, IAMRole.TENANT_OWNER): _TENANT_MANAGE,
    (ResourceType.GROUP, IAMRole.TENANT_MEMBER): _TENANT_READ,
    (ResourceType.GROUP, IAMRole.TENANT_ADMIN): _TENANT_MANAGE,
    (ResourceType.GROUP, IAMRole.TENANT_OWNER): _TENANT_MANAGE,
    (ResourceType.GROUP, IAMRole.GROUP_USER_MEMBER): _TENANT_READ,
    (ResourceType.GROUP, IAMRole.GROUP_GROUP_MEMBER): _TENANT_READ,
    (ResourceType.GROUP, IAMRole.GROUP_OWNER): _TENANT_MANAGE,
    (ResourceType.WORKSPACE, IAMRole.TENANT_MEMBER): _TENANT_READ,
    (ResourceType.WORKSPACE, IAMRole.TENANT_ADMIN): _TENANT_MANAGE,
    (ResourceType.WORKSPACE, IAMRole.TENANT_OWNER): _TENANT_MANAGE,
    (ResourceType.NODE, IAMRole.TENANT_MEMBER): _TENANT_READ,
    (ResourceType.NODE, IAMRole.TENANT_ADMIN): _TENANT_MANAGE,
    (ResourceType.NODE, IAMRole.TENANT_OWNER): _TENANT_MANAGE,
}


def actions_for_roles(resource_type: str, roles: set[IAMRole] | frozenset[IAMRole]) -> frozenset[Action]:
    """Return the union of operations granted by IAM roles for a resource."""
    if IAMRole.SYSTEM_SUPER_ADMIN in roles:
        return frozenset(Action)
    try:
        resource = ResourceType(resource_type.strip().lower())
    except ValueError:
        return frozenset()
    result: set[Action] = set()
    for role in roles:
        result.update(ACL_POLICY_MATRIX.get((resource, role), ()))
    return frozenset(result)


def parse_acl_permission(value: str) -> Action | IAMRole:
    """Parse current and legacy ACL values from persistence."""
    try:
        return Action(value)
    except ValueError:
        return IAMRole(value.strip().lower())


def action_for_role(
    role: SystemAdminRole | TenantMembershipType | GroupMemberType,
) -> IAMRole:
    """Map IAM relationship types to stable ACL actions.

    The role enums all inherit from ``str`` and several contain the same
    value (notably ``TENANT_MEMBERSHIP.OWNER`` and ``GROUP.OWNER``). A single
    dictionary keyed by enum members therefore aliases those roles. Dispatch
    by enum type first so tenant owners can never become group owners.
    """
    if isinstance(role, SystemAdminRole):
        action = {SystemAdminRole.SUPER_ADMIN: IAMRole.SYSTEM_SUPER_ADMIN}[role]
    elif isinstance(role, TenantMembershipType):
        action = {
            TenantMembershipType.MEMBER: IAMRole.TENANT_MEMBER,
            TenantMembershipType.ADMIN: IAMRole.TENANT_ADMIN,
            TenantMembershipType.OWNER: IAMRole.TENANT_OWNER,
        }[role]
    elif isinstance(role, GroupMemberType):
        action = {
            GroupMemberType.USER: IAMRole.GROUP_USER_MEMBER,
            GroupMemberType.GROUP: IAMRole.GROUP_GROUP_MEMBER,
            GroupMemberType.OWNER: IAMRole.GROUP_OWNER,
        }[role]
    else:
        raise TypeError(f"unsupported IAM role: {type(role).__name__}")
    return action


@dataclass(frozen=True, slots=True)
class AccessControlEntry:
    """One effective ACL rule."""

    subject: Subject
    action: Action | IAMRole
    effect: Effect
