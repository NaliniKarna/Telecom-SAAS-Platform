"""sms sender ids

Revision ID: 0013_sms_sender_ids
Revises: 0012_group_type_internal_only
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_sms_sender_ids"
down_revision = "0012_group_type_internal_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_sender_ids",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sender_id", sa.String(20), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("approval_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rejection_reason", sa.String(500), nullable=True),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("sender_id", name="uq_sms_sender_id_sender_id"),
    )
    op.create_index("ix_sms_sender_ids_company_id", "sms_sender_ids", ["company_id"])
    op.create_index("ix_sms_sender_ids_status", "sms_sender_ids", ["status"])
    op.create_index("ix_sms_sender_ids_approval_status", "sms_sender_ids", ["approval_status"])
    op.create_index("ix_sms_sender_ids_is_default", "sms_sender_ids", ["is_default"])


def downgrade() -> None:
    op.drop_index("ix_sms_sender_ids_is_default", "sms_sender_ids")
    op.drop_index("ix_sms_sender_ids_approval_status", "sms_sender_ids")
    op.drop_index("ix_sms_sender_ids_status", "sms_sender_ids")
    op.drop_index("ix_sms_sender_ids_company_id", "sms_sender_ids")
    op.drop_table("sms_sender_ids")
