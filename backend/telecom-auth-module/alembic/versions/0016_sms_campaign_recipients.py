"""sms campaign recipients

Revision ID: 0016_sms_campaign_recipients
Revises: 0015_sms_campaigns
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016_sms_campaign_recipients"
down_revision = "0015_sms_campaigns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_campaign_recipients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sms_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("phone_e164", sa.String(20), nullable=False),
        sa.Column("resolved_name", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("campaign_id", "phone_e164", name="uq_sms_campaign_recipient"),
    )
    op.create_index("ix_sms_campaign_recipients_campaign_id", "sms_campaign_recipients", ["campaign_id"])
    op.create_index("ix_sms_campaign_recipients_phone_e164", "sms_campaign_recipients", ["phone_e164"])


def downgrade() -> None:
    op.drop_index("ix_sms_campaign_recipients_phone_e164", "sms_campaign_recipients")
    op.drop_index("ix_sms_campaign_recipients_campaign_id", "sms_campaign_recipients")
    op.drop_table("sms_campaign_recipients")
