"""contacts

Company-scoped contacts with raw + E.164-normalized numbers, free-form tags,
status, soft-delete.

Revision ID: 0010_contacts
Revises: 0009_api_keys
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_contacts"
down_revision = "0009_api_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    postgresql.ENUM("active", "inactive", "unsubscribed", name="contact_status").create(
        op.get_bind(), checkfirst=True
    )
    postgresql.ENUM("mobile", "landline", "unknown", name="contact_number_type").create(
        op.get_bind(), checkfirst=True
    )
    contact_status = postgresql.ENUM(
        "active", "inactive", "unsubscribed", name="contact_status", create_type=False
    )
    number_type = postgresql.ENUM(
        "mobile", "landline", "unknown", name="contact_number_type", create_type=False
    )

    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=True),
        sa.Column("last_name", sa.String(100), nullable=True),
        sa.Column("mobile_raw", sa.String(40), nullable=True),
        sa.Column("mobile_e164", sa.String(20), nullable=True),
        sa.Column("landline_raw", sa.String(40), nullable=True),
        sa.Column("landline_e164", sa.String(20), nullable=True),
        sa.Column("number_type", number_type, nullable=False, server_default="unknown"),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("status", contact_status, nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"])
    op.create_index("ix_contacts_mobile_e164", "contacts", ["mobile_e164"])
    op.create_index("ix_contacts_landline_e164", "contacts", ["landline_e164"])
    op.create_index("ix_contacts_email", "contacts", ["email"])
    op.create_index("ix_contacts_status", "contacts", ["status"])


def downgrade() -> None:
    op.drop_index("ix_contacts_status", "contacts")
    op.drop_index("ix_contacts_email", "contacts")
    op.drop_index("ix_contacts_landline_e164", "contacts")
    op.drop_index("ix_contacts_mobile_e164", "contacts")
    op.drop_index("ix_contacts_company_id", "contacts")
    op.drop_table("contacts")
    postgresql.ENUM(name="contact_number_type").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="contact_status").drop(op.get_bind(), checkfirst=True)
