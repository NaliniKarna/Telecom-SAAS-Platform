"""sms sender id tenant-scoped uniqueness fix

Corrects the multi-tenant bug where sms_sender_ids.sender_id was UNIQUE globally
(uq_sms_sender_id_sender_id), preventing two companies from registering the same
alphanumeric sender. Replaces it with a per-company unique constraint, and adds
a partial unique index enforcing at most one default sender per company among
live (non-deleted) rows.

Enum-typed columns are intentionally left as String to match migrations
0013-0017 and the ORM models.

Revision ID: 0018_sms_sender_tenant_unique
Revises: 0017_sms_messages
"""
import sqlalchemy as sa
from alembic import op

revision = "0018_sms_sender_tenant_unique"
down_revision = "0017_sms_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the global unique constraint created in 0013 (if present).
    op.execute("ALTER TABLE sms_sender_ids DROP CONSTRAINT IF EXISTS uq_sms_sender_id_sender_id")
    # Per-company uniqueness.
    op.create_unique_constraint(
        "uq_sms_sender_company_value", "sms_sender_ids", ["company_id", "sender_id"]
    )
    # At most one default sender per company (live rows only).
    op.create_index(
        "uq_sms_sender_one_default", "sms_sender_ids", ["company_id"],
        unique=True,
        postgresql_where=sa.text("is_default AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_sms_sender_one_default", table_name="sms_sender_ids")
    op.drop_constraint("uq_sms_sender_company_value", "sms_sender_ids", type_="unique")
    op.create_unique_constraint(
        "uq_sms_sender_id_sender_id", "sms_sender_ids", ["sender_id"]
    )