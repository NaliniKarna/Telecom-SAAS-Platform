"""sms campaigns

Revision ID: 0015_sms_campaigns
Revises: 0014_sms_templates
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015_sms_campaigns"
down_revision = "0014_sms_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sms_sender_ids.id", ondelete="SET NULL"), nullable=True),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sms_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="contacts"),
        sa.Column("schedule_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_recipients", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_sms_campaigns_company_id", "sms_campaigns", ["company_id"])
    op.create_index("ix_sms_campaigns_status", "sms_campaigns", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sms_campaigns_status", "sms_campaigns")
    op.drop_index("ix_sms_campaigns_company_id", "sms_campaigns")
    op.drop_table("sms_campaigns")
