"""IAM SQLAlchemy persistence models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from .....kernel.infrastructure.persistence.sqlalchemy.models import Base


class PrincipalRecord(Base):
    """Polymorphic identity root shared by human and workload principals."""

    __tablename__ = "iam_principals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    principal_type: Mapped[str] = mapped_column(String(32), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    __mapper_args__ = {  # noqa: RUF012
        "polymorphic_on": principal_type,
        "polymorphic_identity": "PRINCIPAL",
    }


class UserRecord(PrincipalRecord):
    __tablename__ = "iam_users"
    id: Mapped[str] = mapped_column(
        String(36), ForeignKey("iam_principals.id"), primary_key=True
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=0)
    __mapper_args__ = {  # noqa: RUF012
        "polymorphic_identity": "USER"
    }


class TenantRecord(Base):
    __tablename__ = "iam_tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=0)


class TenantMembershipRecord(Base):
    __tablename__ = "iam_tenant_memberships"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", name="uq_iam_membership_tenant_user"),
        Index("ix_iam_membership_tenant_active", "tenant_id", "active"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("iam_tenants.id"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("iam_users.id"), index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    membership_type: Mapped[str] = mapped_column(String(16), default="MEMBER")
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=0)


class InvitationRecord(Base):
    __tablename__ = "iam_invitations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    token_hash: Mapped[str] = mapped_column(String(512))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=0)


class SessionRecord(Base):
    __tablename__ = "iam_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    tenant_id: Mapped[str] = mapped_column(String(36), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=0)


class GroupRecord(Base):
    __tablename__ = "iam_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_iam_group_tenant_name"),
        Index("ix_iam_group_tenant", "tenant_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("iam_tenants.id"))
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=0)


class GroupMemberRecord(Base):
    __tablename__ = "iam_group_members"
    __table_args__ = (
        UniqueConstraint(
            "group_id", "member_type", "member_id", name="uq_iam_group_member"
        ),
        Index("ix_iam_group_member_parent", "group_id"),
        Index("ix_iam_group_member_child", "member_type", "member_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    group_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("iam_groups.id", ondelete="CASCADE")
    )
    member_type: Mapped[str] = mapped_column(String(16))
    member_id: Mapped[str] = mapped_column(String(36))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=0)


class SSOProviderRecord(Base):
    __tablename__ = "iam_sso_providers"
    __table_args__ = (UniqueConstraint("issuer", name="uq_iam_sso_provider_issuer"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    issuer: Mapped[str] = mapped_column(String(512))
    client_id: Mapped[str] = mapped_column(String(255))
    client_secret: Mapped[str] = mapped_column(String(1024))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_global: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=0)


class SSOProviderMembershipRecord(Base):
    __tablename__ = "iam_sso_provider_memberships"
    __table_args__ = (
        UniqueConstraint(
            "provider_id", "tenant_id", name="uq_iam_sso_provider_membership"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("iam_sso_providers.id")
    )
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("iam_tenants.id"))


class ExternalSSOIdentityRecord(Base):
    __tablename__ = "iam_external_sso_identities"
    __table_args__ = (
        UniqueConstraint("provider_id", "external_subject", name="uq_iam_sso_subject"),
        Index("ix_iam_sso_identity_user", "user_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("iam_users.id"))
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("iam_sso_providers.id")
    )
    external_subject: Mapped[str] = mapped_column(String(512))
    version: Mapped[int] = mapped_column(Integer, default=0)


class ServicePrincipalRecord(PrincipalRecord):
    __tablename__ = "iam_service_principals"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_iam_service_principal_name"),
        Index("ix_iam_service_principal_tenant", "tenant_id"),
    )
    id: Mapped[str] = mapped_column(
        String(36), ForeignKey("iam_principals.id"), primary_key=True
    )
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("iam_tenants.id"))
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=0)
    __mapper_args__ = {  # noqa: RUF012
        "polymorphic_identity": "SERVICE_PRINCIPAL"
    }


class ApiKeyRecord(Base):
    __tablename__ = "iam_api_keys"
    __table_args__ = (Index("ix_iam_api_key_principal", "principal_id", "revoked"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    principal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("iam_service_principals.id")
    )
    secret_hash: Mapped[str] = mapped_column(String(512))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=0)


class AclRecord(Base):
    __tablename__ = "iam_acls"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "resource_type", "resource_id", name="uq_iam_acl_scope"
        ),
        Index("ix_iam_acl_scope", "tenant_id", "resource_type", "resource_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36))
    resource_type: Mapped[str] = mapped_column(String(255))
    resource_id: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=0)


class AclEntryRecord(Base):
    __tablename__ = "iam_acl_entries"
    __table_args__ = (
        UniqueConstraint(
            "acl_id", "subject_type", "subject_id", "action", name="uq_iam_acl_entry"
        ),
        Index("ix_iam_acl_entry_lookup", "acl_id", "subject_id", "action"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    acl_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("iam_acls.id", ondelete="CASCADE")
    )
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(255))
    effect: Mapped[str] = mapped_column(String(16))


class AclDecisionRecord(Base):
    __tablename__ = "iam_acl_decision_entries"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "resource_type",
            "resource_id",
            "subject_type",
            "subject_id",
            "action",
            name="uq_iam_acl_decision",
        ),
        Index(
            "ix_iam_acl_decision_lookup",
            "tenant_id",
            "resource_type",
            "resource_id",
            "subject_id",
            "action",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(36))
    resource_type: Mapped[str] = mapped_column(String(255))
    resource_id: Mapped[str] = mapped_column(String(255))
    subject_type: Mapped[str] = mapped_column(String(32))
    subject_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(255))
    effect: Mapped[str] = mapped_column(String(16))
    source_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
