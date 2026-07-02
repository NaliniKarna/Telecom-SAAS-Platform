"""company change requests (settings approval workflow)

Adds the company_change_requests table backing the approval workflow for gated
company-settings fields (name, contact_email, contact_phone). A partial unique
index enforces at most one PENDING request per company.

Revision ID: 0007_company_change_requests
Revises: 0006_user_avatar_url
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_company_change_requests"
down_revision = "0006_user_avatar_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    change_request_status = postgresql.ENUM(
        "pending", "approved", "rejected",
        name="change_request_status",
        create_type=False,  # we create it explicitly below; don't auto-create
    )
    postgresql.ENUM(
        "pending", "approved", "rejected",
        name="change_request_status",
    ).create(op.get_bind(), checkfirst=True)

    op.create_table(
        "company_change_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "requested_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "status", change_request_status,
            nullable=False, server_default="pending",
        ),
        sa.Column(
            "changes", postgresql.JSONB(), nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "reviewed_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.String(500), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
    )
    op.create_index(
        "ix_company_change_requests_company_id",
        "company_change_requests", ["company_id"],
    )
    op.create_index(
        "ix_company_change_requests_status",
        "company_change_requests", ["status"],
    )
    # At most one PENDING request per company.
    op.create_index(
        "uq_company_change_requests_one_pending",
        "company_change_requests", ["company_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("uq_company_change_requests_one_pending", "company_change_requests")
    op.drop_index("ix_company_change_requests_status", "company_change_requests")
    op.drop_index("ix_company_change_requests_company_id", "company_change_requests")
    op.drop_table("company_change_requests")
    postgresql.ENUM(name="change_request_status").drop(op.get_bind(), checkfirst=True)
