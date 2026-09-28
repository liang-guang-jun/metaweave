"""Store the explicit system administrator role type."""

from __future__ import annotations

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0007_system_admin_roles"
down_revision = "0006_membership_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "iam_system_admins",
        sa.Column("role", sa.String(32), nullable=False, server_default="SUPER_ADMIN"),
    )
    op.add_column(
        "iam_system_admins",
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )

    # Existing relationship rows must receive their ACL representation before
    # application authorization starts consulting ACLs as the source of truth.
    connection = op.get_bind()
    membership_result = connection.execute(
        sa.text(
            "SELECT tenant_id, user_id, membership_type "
            "FROM iam_tenant_memberships WHERE active = TRUE"
        )
    )
    if membership_result is None:
        return
    membership_rows = list(membership_result.mappings())
    for row in membership_rows:
        tenant_id = str(row["tenant_id"])
        scope = connection.execute(
            sa.text(
                "SELECT id FROM iam_acls WHERE tenant_id = :tenant_id "
                "AND resource_type = 'tenant' AND resource_id = :resource_id"
            ),
            {"tenant_id": tenant_id, "resource_id": tenant_id},
        ).scalar_one_or_none()
        if scope is None:
            scope = str(uuid4())
            connection.execute(
                sa.text(
                    "INSERT INTO iam_acls "
                    "(id, tenant_id, resource_type, resource_id, version) "
                    "VALUES (:id, :tenant_id, 'tenant', :resource_id, 1)"
                ),
                {"id": scope, "tenant_id": tenant_id, "resource_id": tenant_id},
            )
        connection.execute(
            sa.text(
                "INSERT INTO iam_acl_entries "
                "(acl_id, subject_type, subject_id, action, effect) "
                "SELECT :acl_id, 'USER', :user_id, :action, 'ALLOW' "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM iam_acl_entries "
                "WHERE acl_id = :acl_id AND subject_type = 'USER' "
                "AND subject_id = :user_id AND action = :action"
                ")"
            ),
            {
                "acl_id": scope,
                "user_id": str(row["user_id"]),
                "action": {
                    "MEMBER": "tenant.member",
                    "ADMIN": "tenant.admin",
                    "OWNER": "tenant.owner",
                }.get(str(row["membership_type"]), "tenant.member"),
            },
        )

    system_scope = connection.execute(
        sa.text(
            "SELECT id FROM iam_acls WHERE tenant_id = :tenant_id "
            "AND resource_type = 'system' AND resource_id = 'instance'"
        ),
        {"tenant_id": "00000000-0000-0000-0000-000000000000"},
    ).scalar_one_or_none()
    if system_scope is None:
        system_scope = str(uuid4())
        connection.execute(
            sa.text(
                "INSERT INTO iam_acls "
                "(id, tenant_id, resource_type, resource_id, version) "
                "VALUES (:id, :tenant_id, 'system', 'instance', 1)"
            ),
            {
                "id": system_scope,
                "tenant_id": "00000000-0000-0000-0000-000000000000",
            },
        )
    for row in list(
        connection.execute(
            sa.text("SELECT user_id FROM iam_system_admins WHERE active = TRUE")
        ).mappings()
    ):
        connection.execute(
            sa.text(
                "INSERT INTO iam_acl_entries "
                "(acl_id, subject_type, subject_id, action, effect) "
                "SELECT :acl_id, 'USER', :user_id, 'system.super_admin', 'ALLOW' "
                "WHERE NOT EXISTS ("
                "SELECT 1 FROM iam_acl_entries "
                "WHERE acl_id = :acl_id AND subject_type = 'USER' "
                "AND subject_id = :user_id AND action = 'system.super_admin'"
                ")"
            ),
            {"acl_id": system_scope, "user_id": str(row["user_id"])},
        )


def downgrade() -> None:
    op.drop_column("iam_system_admins", "version")
    op.drop_column("iam_system_admins", "role")
