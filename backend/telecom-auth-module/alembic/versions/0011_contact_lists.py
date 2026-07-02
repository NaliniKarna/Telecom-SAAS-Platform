"""contact lists

Dedicated contact_lists + contact_list_members (membership FKs to contacts, not
users). Soft-delete on lists; one membership row per (list, contact).

Revision ID: 0011_contact_lists
Revises: 0010_contacts
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_contact_lists"
down_revision = "0010_contacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_lists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_contact_lists_company_id", "contact_lists", ["company_id"])

    op.create_table(
        "contact_list_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("list_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("contact_lists.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("list_id", "contact_id", name="uq_contact_list_member"),
    )
    op.create_index("ix_contact_list_members_list_id", "contact_list_members", ["list_id"])
    op.create_index("ix_contact_list_members_contact_id", "contact_list_members", ["contact_id"])


def downgrade() -> None:
    op.drop_index("ix_contact_list_members_contact_id", "contact_list_members")
    op.drop_index("ix_contact_list_members_list_id", "contact_list_members")
    op.drop_table("contact_list_members")
    op.drop_index("ix_contact_lists_company_id", "contact_lists")
    op.drop_table("contact_lists")
