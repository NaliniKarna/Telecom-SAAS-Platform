"""sms templates

Revision ID: 0014_sms_templates
Revises: 0013_sms_sender_ids
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014_sms_templates"
down_revision = "0013_sms_sender_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("body", sa.String(4000), nullable=False),
        sa.Column("variables", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_sms_templates_company_id", "sms_templates", ["company_id"])
    op.create_index("ix_sms_templates_status", "sms_templates", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sms_templates_status", "sms_templates")
    op.drop_index("ix_sms_templates_company_id", "sms_templates")
    op.drop_table("sms_templates")
