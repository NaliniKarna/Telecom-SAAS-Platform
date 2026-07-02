"""user avatar_url

Adds an optional profile-photo URL to users (the URL points at whatever storage
backend is active; the column is storage-agnostic).

Revision ID: 0006_user_avatar_url
Revises: 0005_company_profile_fields
"""
import sqlalchemy as sa
from alembic import op

revision = "0006_user_avatar_url"
down_revision = "0005_company_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
