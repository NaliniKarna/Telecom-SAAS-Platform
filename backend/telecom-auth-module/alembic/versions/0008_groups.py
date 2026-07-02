"""groups and group_members

Adds organizational groups (tenant-scoped, soft-deletable) and a many-to-many
group_members association. Groups do NOT grant permissions; authorization stays
with RBAC. group_type (internal/contact) supports future Contacts/SMS/Voice/
Missed-Call/Campaign modules without separate group models.

Revision ID: 0008_groups
Revises: 0007_company_change_requests
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_groups"
down_revision = "0007_company_change_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    group_status = postgresql.ENUM(
        "active", "inactive", name="group_status", create_type=False,
    )
    group_type = postgresql.ENUM(
        "internal", "contact", name="group_type", create_type=False,
    )
    postgresql.ENUM("active", "inactive", name="group_status").create(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM("internal", "contact", name="group_type").create(
        op.get_bind(), checkfirst=True
    )

    op.create_table(
        "groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("status", group_status, nullable=False, server_default="active"),
        sa.Column("group_type", group_type, nullable=False, server_default="internal"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_groups_company_id", "groups", ["company_id"])
    op.create_index("ix_groups_status", "groups", ["status"])
    op.create_index("ix_groups_group_type", "groups", ["group_type"])

    op.create_table(
        "group_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "group_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("groups.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("group_id", "user_id", name="uq_group_member"),
    )
    op.create_index("ix_group_members_group_id", "group_members", ["group_id"])
    op.create_index("ix_group_members_user_id", "group_members", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_group_members_user_id", "group_members")
    op.drop_index("ix_group_members_group_id", "group_members")
    op.drop_table("group_members")
    op.drop_index("ix_groups_group_type", "groups")
    op.drop_index("ix_groups_status", "groups")
    op.drop_index("ix_groups_company_id", "groups")
    op.drop_table("groups")
    postgresql.ENUM(name="group_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="group_status").drop(op.get_bind(), checkfirst=True)
