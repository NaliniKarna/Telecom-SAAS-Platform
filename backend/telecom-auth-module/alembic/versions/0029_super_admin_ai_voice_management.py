"""super admin ai voice management: plan-voice availability

Adds the Super Admin AI Voice management layer's schema needs:

  subscription_plan_voices — which voices (ai_voices) a subscription plan
  makes available to the companies on it. A plan with zero rows here grants
  NO global voices to its companies (safe default for any newly created
  plan). Backfilled below for every pre-existing active plan against every
  pre-existing active global voice, so this new restriction doesn't take
  voice access away from any company that already had it working before
  this table existed.

  subscription_plans.default_monthly_tts_characters — the "minimum
  required usage tracking" identified for this phase: a ceiling value only
  (NULL = unlimited), matching the existing default_monthly_sms_limit /
  default_monthly_voice_minutes convention exactly. Not enforced by a
  counter — no per-company usage-metering mechanism exists anywhere in
  this codebase yet (those two aren't enforced either); building one now
  would be the "large billing/usage platform" this phase was told not to
  build.

Revision ID: 0029
Revises: 0028
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscription_plan_voices",
        sa.Column(
            "plan_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("subscription_plans.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "voice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_voices.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    op.add_column(
        "subscription_plans",
        sa.Column("default_monthly_tts_characters", sa.Integer(), nullable=True),
    )

    # Backfill: every plan that exists today gets every currently-active
    # global voice. Companies that already had working TTS keep working
    # exactly as before; Super Admin can curate (narrow or widen) from here.
    op.execute(
        """
        INSERT INTO subscription_plan_voices (plan_id, voice_id)
        SELECT p.id, v.id
        FROM subscription_plans p
        CROSS JOIN ai_voices v
        WHERE v.company_id IS NULL
          AND v.status = 'active'
          AND v.deleted_at IS NULL
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_column("subscription_plans", "default_monthly_tts_characters")
    op.drop_table("subscription_plan_voices")
