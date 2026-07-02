"""sms message analytics indexes

Indexes supporting tracking + analytics aggregations:
  - (company_id, status)  : status_counts / delivery-rate per tenant,
  - (company_id, sent_at) : messages-sent-today + date-range filters,
  - provider_message_id   : delivery-callback lookups.

Additive only. Idempotent (IF NOT EXISTS) so it is safe to re-run after a
partially-applied attempt.

Revision ID: 0020
Revises: 0019
"""
from alembic import op

# Keep revision ids short: the alembic_version column is VARCHAR(32).
revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sms_messages_company_status "
        "ON sms_messages (company_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sms_messages_company_sent_at "
        "ON sms_messages (company_id, sent_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_sms_messages_provider_msg_id "
        "ON sms_messages (provider_message_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_sms_messages_provider_msg_id")
    op.execute("DROP INDEX IF EXISTS ix_sms_messages_company_sent_at")
    op.execute("DROP INDEX IF EXISTS ix_sms_messages_company_status")