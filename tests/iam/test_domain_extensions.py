from uuid import uuid4

import pytest

from server.iam.domain import (
    ACL_POLICY_MATRIX,
    AccessControlEntry,
    AccessDecisionEvaluator,
    AclScope,
    Action,
    Effect,
    GroupId,
    GroupMemberType,
    GroupNestingGuard,
    IamDomainError,
    IAMRole,
    ResourceType,
    RoleAction,
    Subject,
    SubjectType,
    SystemAdminRole,
    TenantId,
    TenantMembershipType,
    UserId,
    action_for_role,
)


def test_subject_supports_group_and_service_identity_shape() -> None:
    subject = Subject(GroupId(uuid4()), SubjectType.GROUP)
    assert subject.subject_type is SubjectType.GROUP


def test_group_nesting_guard_rejects_transitive_cycle() -> None:
    parent, child, leaf = GroupId(uuid4()), GroupId(uuid4()), GroupId(uuid4())
    with pytest.raises(IamDomainError):
        GroupNestingGuard.ensure_acyclic(
            parent, child, {child: frozenset({leaf}), leaf: frozenset({parent})}
        )


def test_acl_entry_keeps_explicit_deny_effect() -> None:
    entry = AccessControlEntry(
        Subject(UserId(uuid4())), Action("READ"), Effect.DENY
    )
    assert entry.action.value == "read"
    assert entry.effect is Effect.DENY


def test_iam_relationship_types_map_to_stable_acl_actions() -> None:
    assert RoleAction is IAMRole
    assert Action.READ.value == "read"
    assert Action.CREATE.value == "create"
    assert Action.UPDATE.value == "update"
    assert Action.DELETE.value == "delete"
    assert Action.MANAGE.value == "manage"
    assert action_for_role(SystemAdminRole.SUPER_ADMIN).value == RoleAction.SYSTEM_SUPER_ADMIN.value
    assert action_for_role(TenantMembershipType.ADMIN).value == RoleAction.TENANT_ADMIN.value
    assert action_for_role(TenantMembershipType.OWNER).value == RoleAction.TENANT_OWNER.value
    assert action_for_role(GroupMemberType.OWNER).value == RoleAction.GROUP_OWNER.value


def _role_entry(subject: Subject, role: IAMRole) -> AccessControlEntry:
    return AccessControlEntry(subject, role, Effect.ALLOW)


def _evaluate(
    subject: Subject,
    role: IAMRole,
    action: Action,
    *,
    extra_subjects: set[Subject] | None = None,
    active: bool = True,
):
    evaluator = AccessDecisionEvaluator()
    resource_type = "group" if role.value.startswith("group.") else "tenant"
    scope = AclScope(TenantId(uuid4()), resource_type, "resource-1")
    subjects = {subject, *(extra_subjects or set())}
    return evaluator.authorize(
        subject=subject,
        action=action,
        resource_scope=scope,
        resource_entries=[_role_entry(subject if role is not IAMRole.GROUP_GROUP_MEMBER else next(iter(extra_subjects or {subject})), role)],
        type_entries=[],
        membership_active=active,
        subjects=subjects,
    )


def test_tenant_roles_follow_policy_matrix() -> None:
    subject = Subject(UserId(uuid4()))
    assert not _evaluate(subject, IAMRole.TENANT_MEMBER, Action.UPDATE).permit
    assert _evaluate(subject, IAMRole.TENANT_ADMIN, Action.UPDATE).permit
    assert _evaluate(subject, IAMRole.TENANT_OWNER, Action.MANAGE).permit
    assert ACL_POLICY_MATRIX[(ResourceType.TENANT, IAMRole.TENANT_MEMBER)] == frozenset({Action.READ})


def test_group_user_and_nested_group_members_are_distinct() -> None:
    user = Subject(UserId(uuid4()))
    nested_group = Subject(GroupId(uuid4()), SubjectType.GROUP)
    assert _evaluate(user, IAMRole.GROUP_USER_MEMBER, Action.READ).permit
    assert not _evaluate(user, IAMRole.GROUP_USER_MEMBER, Action.UPDATE).permit
    assert _evaluate(
        user,
        IAMRole.GROUP_GROUP_MEMBER,
        Action.READ,
        extra_subjects={nested_group},
    ).permit
    assert IAMRole.GROUP_USER_MEMBER is not IAMRole.GROUP_GROUP_MEMBER


def test_group_owner_and_system_super_admin_bypass() -> None:
    subject = Subject(UserId(uuid4()))
    assert _evaluate(subject, IAMRole.GROUP_OWNER, Action.DELETE).permit
    evaluator = AccessDecisionEvaluator()
    decision = evaluator.authorize(
        subject=subject,
        action=Action.MANAGE,
        resource_scope=AclScope(TenantId(uuid4()), "workspace", "workspace-1"),
        resource_entries=[],
        type_entries=[_role_entry(subject, IAMRole.SYSTEM_SUPER_ADMIN)],
        membership_active=False,
    )
    assert decision.permit
    assert decision.reason == "system_super_admin_bypass"


def test_unauthorized_action_is_denied() -> None:
    subject = Subject(UserId(uuid4()))
    decision = _evaluate(subject, IAMRole.GROUP_USER_MEMBER, Action.DELETE)
    assert not decision.permit
    assert decision.reason == "no_matching_rule"
