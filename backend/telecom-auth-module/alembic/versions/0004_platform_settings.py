"""platform_settings table (singleton config)

Creates the single-row platform settings table and seeds the one row with
sensible defaults. down_revision is 0003 (subscription plan fields).

Revision ID: 0004_platform_settings
Revises: 0003_subscription_plan_fields
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_platform_settings"
down_revision = "0003_subscription_plan_fields"
branch_labels = None
depends_on = None

_SINGLETON_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "platform_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform_name", sa.String(200), nullable=False,
                  server_default="Telecom Platform"),
        sa.Column("platform_logo_url", sa.Text(), nullable=True),
        sa.Column("support_email", sa.String(255), nullable=True),
        sa.Column("support_phone", sa.String(30), nullable=True),
        sa.Column("default_plan_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("default_user_limit", sa.Integer(), nullable=True),
        sa.Column("default_api_key_limit", sa.Integer(), nullable=True),
        sa.Column("default_api_rate_limit", sa.Integer(), nullable=True),
        sa.Column("sms_module_enabled", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("voice_module_enabled", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("missed_call_module_enabled", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("api_access_module_enabled", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("jwt_expiry_minutes", sa.Integer(), nullable=False,
                  server_default="15"),
        sa.Column("password_min_length", sa.Integer(), nullable=False,
                  server_default="8"),
        sa.Column("password_require_uppercase", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("password_require_number", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("password_require_symbol", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    # Seed the single settings row (server defaults populate the rest).
    op.execute(
        f"INSERT INTO platform_settings (id) VALUES ('{_SINGLETON_ID}')"
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
