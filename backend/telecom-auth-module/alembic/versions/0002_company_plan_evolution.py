"""company plan/entitlements/limits/contact evolution

- create subscription_plans + seed default tiers
- add companies.plan_id FK (+ contact, entitlement, limit columns)
- backfill plan_id from the old free-text companies.plan
- drop companies.plan

Revision ID: 0002_company_plan_evolution
Revises: 0001_baseline
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_company_plan_evolution"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


# Default plan tiers. (code, name, max_users, api_rate_limit,
#                      sms, voice, missed_call, freepbx)
_PLANS = [
    ("free", "Free", 5, 60, False, False, False, False),
    ("pro", "Pro", 50, 600, True, True, True, False),
    ("enterprise", "Enterprise", None, 6000, True, True, True, True),
]


def upgrade() -> None:
    # 1. subscription_plans table -------------------------------------------
    op.create_table(
        "subscription_plans",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("default_max_users", sa.Integer(), nullable=True),
        sa.Column("default_api_rate_limit", sa.Integer(), nullable=True),
        sa.Column("default_sms_enabled", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("default_voice_enabled", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("default_missed_call_enabled", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("default_freepbx_enabled", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # 2. seed default plans (capture ids for backfill) ----------------------
    plans_table = sa.table(
        "subscription_plans",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("default_max_users", sa.Integer),
        sa.column("default_api_rate_limit", sa.Integer),
        sa.column("default_sms_enabled", sa.Boolean),
        sa.column("default_voice_enabled", sa.Boolean),
        sa.column("default_missed_call_enabled", sa.Boolean),
        sa.column("default_freepbx_enabled", sa.Boolean),
    )
    code_to_id: dict[str, uuid.UUID] = {}
    rows = []
    for code, name, mu, rl, sms, voice, mc, pbx in _PLANS:
        pid = uuid.uuid4()
        code_to_id[code] = pid
        rows.append({
            "id": pid, "code": code, "name": name,
            "default_max_users": mu, "default_api_rate_limit": rl,
            "default_sms_enabled": sms, "default_voice_enabled": voice,
            "default_missed_call_enabled": mc, "default_freepbx_enabled": pbx,
        })
    op.bulk_insert(plans_table, rows)

    # 3. add new company columns (all nullable / defaulted -> safe online) ---
    op.add_column("companies", sa.Column(
        "plan_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_companies_plan", "companies", "subscription_plans",
        ["plan_id"], ["id"], ondelete="RESTRICT",
    )
    op.create_index("idx_companies_plan", "companies", ["plan_id"])

    op.add_column("companies", sa.Column(
        "contact_email", postgresql.CITEXT(), nullable=True))
    op.add_column("companies", sa.Column(
        "contact_phone", sa.String(30), nullable=True))

    for col in ("sms_enabled", "voice_enabled", "missed_call_enabled",
                "freepbx_enabled"):
        op.add_column("companies", sa.Column(
            col, sa.Boolean(), nullable=False, server_default=sa.false()))

    op.add_column("companies", sa.Column("max_users", sa.Integer(), nullable=True))
    op.add_column("companies", sa.Column(
        "api_rate_limit", sa.Integer(), nullable=True))

    # 4. backfill plan_id from the old free-text plan -----------------------
    # Map known codes; anything unrecognized falls back to 'free'.
    free_id = code_to_id["free"]
    for code, pid in code_to_id.items():
        op.execute(
            sa.text(
                "UPDATE companies SET plan_id = :pid WHERE lower(plan) = :code"
            ).bindparams(pid=pid, code=code)
        )
    op.execute(
        sa.text(
            "UPDATE companies SET plan_id = :pid WHERE plan_id IS NULL"
        ).bindparams(pid=free_id)
    )

    # 5. drop the old free-text column --------------------------------------
    op.drop_column("companies", "plan")


def downgrade() -> None:
    # Re-add the free-text plan column and backfill from plan code.
    op.add_column("companies", sa.Column(
        "plan", sa.String(50), nullable=False, server_default="free"))
    op.execute(sa.text(
        "UPDATE companies c SET plan = p.code "
        "FROM subscription_plans p WHERE c.plan_id = p.id"
    ))

    op.drop_column("companies", "api_rate_limit")
    op.drop_column("companies", "max_users")
    for col in ("freepbx_enabled", "missed_call_enabled", "voice_enabled",
                "sms_enabled"):
        op.drop_column("companies", col)
    op.drop_column("companies", "contact_phone")
    op.drop_column("companies", "contact_email")

    op.drop_index("idx_companies_plan", table_name="companies")
    op.drop_constraint("fk_companies_plan", "companies", type_="foreignkey")
    op.drop_column("companies", "plan_id")

    op.drop_table("subscription_plans")
    # Remove the server_default we added on re-created plan column.
    op.alter_column("companies", "plan", server_default=None)
