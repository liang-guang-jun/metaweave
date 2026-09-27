"""IAM domain services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .errors import IamDomainError
from .value_objects import (
    AccessControlEntry,
    Action,
    AclScope,
    Effect,
    IAMRole,
    Subject,
    actions_for_roles,
)


class AclMergeService:
    """Merge resource and type ACLs with resource precedence and deny priority."""

    @staticmethod
    def merge(
        resource_entries: Iterable[AccessControlEntry],
        type_entries: Iterable[AccessControlEntry],
    ) -> tuple[AccessControlEntry, ...]:
        resource_entries = tuple(resource_entries)
        type_entries = tuple(type_entries)
        result: dict[tuple[Subject, object], AccessControlEntry] = {}
        for entry in type_entries:
            result[(entry.subject, entry.action)] = entry
        for entry in resource_entries:
            result[(entry.subject, entry.action)] = entry
        type_by_key: dict[tuple[Subject, Action | IAMRole], list[AccessControlEntry]] = {}
        resource_by_key: dict[tuple[Subject, Action | IAMRole], list[AccessControlEntry]] = {}
        for entry in type_entries:
            type_by_key.setdefault((entry.subject, entry.action), []).append(entry)
        for entry in resource_entries:
            resource_by_key.setdefault((entry.subject, entry.action), []).append(entry)
        for key, entries in type_by_key.items():
            if key not in resource_by_key and any(
                entry.effect is Effect.DENY for entry in entries
            ):
                result[key] = next(
                    entry for entry in entries if entry.effect is Effect.DENY
                )
        for key, entries in resource_by_key.items():
            if any(entry.effect is Effect.DENY for entry in entries):
                result[key] = next(
                    entry for entry in entries if entry.effect is Effect.DENY
                )
        return tuple(result.values())


@dataclass(frozen=True, slots=True)
class AccessDecision:
    """A deterministic authorization result."""

    permit: bool
    reason: str
    scope: AclScope | None = None


class AccessDecisionEvaluator:
    """Evaluate ACL entries after membership has been checked by the caller."""

    def authorize(
        self,
        *,
        subject: Subject,
        resource_scope: AclScope,
        action: Action,
        resource_entries: Iterable[AccessControlEntry],
        type_entries: Iterable[AccessControlEntry],
        membership_active: bool,
        subjects: Iterable[Subject] | None = None,
    ) -> AccessDecision:
        """Compatibility-friendly authorization entry point.

        Callers may use ``authorize`` as the semantic API while older callers
        continue to use ``evaluate``. The orchestration layer is responsible
        for resolving relationships and passing the resulting entries.
        """
        return self.evaluate(
            subject,
            action,
            resource_scope,
            resource_entries,
            type_entries,
            membership_active,
            subjects,
        )

    def evaluate(
        self,
        subject: Subject,
        action: Action,
        resource_scope: AclScope,
        resource_entries: Iterable[AccessControlEntry],
        type_entries: Iterable[AccessControlEntry],
        membership_active: bool,
        subjects: Iterable[Subject] | None = None,
    ) -> AccessDecision:
        effective_subjects = frozenset(subjects or (subject,))
        all_entries = tuple(resource_entries) + tuple(type_entries)
        relationship_roles = {
            entry.action
            for entry in all_entries
            if (
                entry.subject in effective_subjects
                and entry.effect is Effect.ALLOW
                and isinstance(entry.action, IAMRole)
            )
        }
        denied_roles = {
            entry.action
            for entry in all_entries
            if (
                entry.subject in effective_subjects
                and entry.effect is Effect.DENY
                and isinstance(entry.action, IAMRole)
            )
        }
        relationship_roles.difference_update(denied_roles)
        if IAMRole.SYSTEM_SUPER_ADMIN in relationship_roles:
            return AccessDecision(True, "system_super_admin_bypass", resource_scope)
        if not membership_active:
            return AccessDecision(False, "inactive_membership")
        resource_matching = [
            entry
            for entry in resource_entries
            if entry.subject in effective_subjects and entry.action == action
        ]
        type_matching = [
            entry
            for entry in type_entries
            if entry.subject in effective_subjects and entry.action == action
        ]
        # A resource rule shadows the type rule, while DENY wins among rules
        # within the same scope.
        matching = resource_matching or type_matching
        if not matching:
            if action in actions_for_roles(resource_scope.resource_type, relationship_roles):
                return AccessDecision(True, "role_policy", resource_scope)
            return AccessDecision(False, "no_matching_rule")
        entry = next(
            (candidate for candidate in matching if candidate.effect is Effect.DENY),
            matching[0],
        )
        scope = (
            resource_scope
            if resource_matching
            else AclScope(
                resource_scope.tenant_id,
                resource_scope.resource_type,
                "*",
            )
        )
        return AccessDecision(
            entry.effect is Effect.ALLOW, entry.effect.value.lower(), scope
        )


class LastAdminGuard:
    """Prevent a tenant from losing its final active administrator."""

    @staticmethod
    def ensure_not_last_admin(*, removing_admin: bool, active_admin_count: int) -> None:
        if removing_admin and active_admin_count <= 1:
            raise IamDomainError(
                "cannot remove or demote the last active administrator"
            )


class PasswordPolicyValidator:
    """Validate plaintext passwords before hashing."""

    def __init__(
        self,
        min_length: int = 12,
        require_upper: bool = True,
        require_digit: bool = True,
        require_symbol: bool = True,
    ) -> None:
        self.min_length = min_length
        self.require_upper = require_upper
        self.require_digit = require_digit
        self.require_symbol = require_symbol

    def validate(self, password: str) -> None:
        if len(password) < self.min_length:
            raise IamDomainError("password does not satisfy policy")
        if self.require_upper and not any(char.isupper() for char in password):
            raise IamDomainError("password does not satisfy policy")
        if self.require_digit and not any(char.isdigit() for char in password):
            raise IamDomainError("password does not satisfy policy")
        if self.require_symbol and not any(not char.isalnum() for char in password):
            raise IamDomainError("password does not satisfy policy")


class OidcClaimsValidator:
    """Validate the minimal claims required from an OIDC adapter."""

    @staticmethod
    def validate(*, subject: str, email: str) -> None:
        if not subject.strip() or "@" not in email:
            raise IamDomainError("invalid OIDC identity")


class GroupNestingGuard:
    """Reject group graphs that would form a membership cycle."""

    @staticmethod
    def ensure_acyclic(
        parent_id: object,
        child_id: object,
        child_groups: dict[object, frozenset[object]],
    ) -> None:
        """Raise when adding child_id under parent_id makes a directed cycle."""
        frontier = [child_id]
        visited: set[object] = set()
        while frontier:
            current = frontier.pop()
            if current == parent_id:
                raise IamDomainError("group nesting would create a cycle")
            if current in visited:
                continue
            visited.add(current)
            frontier.extend(child_groups.get(current, frozenset()))
