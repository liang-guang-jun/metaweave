"""Shared IAM HTTP conversion helpers."""

from __future__ import annotations

from ...application.dto import MembershipDTO


def membership_response(value: MembershipDTO) -> dict[str, object]:
    """Convert an application membership DTO to JSON-safe values."""
    return {
        "membership_id": str(value.membership_id),
        "tenant_id": str(value.tenant_id),
        "user_id": str(value.user_id),
        "active": value.active,
        "is_admin": value.is_admin,
        "membership_type": value.membership_type.value,
    }
