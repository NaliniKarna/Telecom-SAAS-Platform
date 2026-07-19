"""add contact extended fields (company_name, designation, contact_type)

Supports CSV import fields: Company / Individual type, Company Name,
Designation / Role. These columns are nullable and optional — existing
contacts are unaffected.

Revision ID: 0026
Revises: 0025
"""
import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column(
            "contact_type",
            sa.String(20),
            nullable=True,
            server_default=None,
            comment="individual or company",
        ),
    )
    op.add_column(
        "contacts",
        sa.Column(
            "company_name",
            sa.String(255),
            nullable=True,
        ),
    )
    op.add_column(
        "contacts",
        sa.Column(
            "designation",
            sa.String(255),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("contacts", "designation")
    op.drop_column("contacts", "company_name")
    op.drop_column("contacts", "contact_type")
