"""subscription_plans: additive fields for plan management

Adds description, extra default limits (api keys, monthly sms/voice), api access
entitlement, and created_by/updated_by attribution. All additive and nullable /
defaulted, so it applies safely to existing rows. Also adds a UNIQUE constraint
on name (plan names must be unique).

Revision ID: 0003_subscription_plan_fields
Revises: 0002_company_plan_evolution
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_subscription_plan_fields"
down_revision = "0002_company_plan_evolution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "subscription_plans", sa.Column("description", sa.Text(), nullable=True)
    )
    op.add_column(
        "subscription_plans",
        sa.Column("default_max_api_keys", sa.Integer(), nullable=True),
    )
    op.add_column(
        "subscription_plans",
        sa.Column("default_monthly_sms_limit", sa.Integer(), nullable=True),
    )
    op.add_column(
        "subscription_plans",
        sa.Column("default_monthly_voice_minutes", sa.Integer(), nullable=True),
    )
    op.add_column(
        "subscription_plans",
        sa.Column(
            "default_api_access_enabled", sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "subscription_plans",
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "subscription_plans",
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Soft-delete support for plans.
    op.add_column(
        "subscription_plans",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Plan names must be unique (codes already are).
    op.create_unique_constraint(
        "uq_subscription_plans_name", "subscription_plans", ["name"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_subscription_plans_name", "subscription_plans", type_="unique"
    )
    op.drop_column("subscription_plans", "deleted_at")
    op.drop_column("subscription_plans", "updated_by")
    op.drop_column("subscription_plans", "created_by")
    op.drop_column("subscription_plans", "default_api_access_enabled")
    op.drop_column("subscription_plans", "default_monthly_voice_minutes")
    op.drop_column("subscription_plans", "default_monthly_sms_limit")
    op.drop_column("subscription_plans", "default_max_api_keys")
    op.drop_column("subscription_plans", "description")
