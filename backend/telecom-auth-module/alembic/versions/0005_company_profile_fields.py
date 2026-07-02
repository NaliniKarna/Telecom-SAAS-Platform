"""company profile fields (address, timezone, logo_url)

Adds editable company-profile/branding columns used by the Company Settings
screen. All nullable, no backfill needed.

Revision ID: 0005_company_profile_fields
Revises: 0004_platform_settings
"""
import sqlalchemy as sa
from alembic import op

revision = "0005_company_profile_fields"
down_revision = "0004_platform_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("address", sa.String(500), nullable=True))
    op.add_column("companies", sa.Column("timezone", sa.String(64), nullable=True))
    op.add_column("companies", sa.Column("logo_url", sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "logo_url")
    op.drop_column("companies", "timezone")
    op.drop_column("companies", "address")
