"""sms campaign source list column + performance indexes

Adds:
  - sms_campaigns.source_list_id  (FK -> contact_lists, SET NULL): the chosen
    list when source_type = 'contact_list'. (Individual-contact selections are
    persisted as snapshot rows in sms_campaign_recipients.)
  - composite index on (company_id, status) for campaign history listing,
  - index on sms_campaign_recipients.campaign_id for recipient lookups.

Additive only — safe to apply on top of the existing 0013-0018 chain.

Revision ID: 0019
Revises: 0018_sms_sender_tenant_unique
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0019"
down_revision = "0018_sms_sender_tenant_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sms_campaigns",
        sa.Column("source_list_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("contact_lists.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_sms_campaigns_company_status", "sms_campaigns", ["company_id", "status"])
    op.create_index("ix_sms_campaign_recipients_campaign", "sms_campaign_recipients", ["campaign_id"])
    op.create_index("ix_sms_messages_campaign", "sms_messages", ["campaign_id"])


def downgrade() -> None:
    op.drop_index("ix_sms_messages_campaign", table_name="sms_messages")
    op.drop_index("ix_sms_campaign_recipients_campaign", table_name="sms_campaign_recipients")
    op.drop_index("ix_sms_campaigns_company_status", table_name="sms_campaigns")
    op.drop_column("sms_campaigns", "source_list_id")
