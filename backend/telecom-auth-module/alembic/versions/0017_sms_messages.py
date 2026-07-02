"""sms messages

Revision ID: 0017_sms_messages
Revises: 0016_sms_campaign_recipients
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017_sms_messages"
down_revision = "0016_sms_campaign_recipients"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sms_campaigns.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recipient_phone", sa.String(20), nullable=False),
        sa.Column("sender_id", sa.String(20), nullable=True),
        sa.Column("content", sa.String(4000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("error_details", sa.String(1000), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_sms_messages_company_id", "sms_messages", ["company_id"])
    op.create_index("ix_sms_messages_campaign_id", "sms_messages", ["campaign_id"])
    op.create_index("ix_sms_messages_recipient_phone", "sms_messages", ["recipient_phone"])
    op.create_index("ix_sms_messages_status", "sms_messages", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sms_messages_status", "sms_messages")
    op.drop_index("ix_sms_messages_recipient_phone", "sms_messages")
    op.drop_index("ix_sms_messages_campaign_id", "sms_messages")
    op.drop_index("ix_sms_messages_company_id", "sms_messages")
    op.drop_table("sms_messages")
