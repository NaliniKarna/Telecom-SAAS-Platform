"""voice campaign execution: recipient attempts (Phase 4B)

Adds:
  voice_campaign_recipients.attempt_count — current attempt number, bumped
    only by a manual retry (default 1).
  voice_campaign_recipient_attempts       — one row per execution attempt,
    unique on execution_key (the durable idempotency anchor for Kafka
    redelivery — see app/models/voice_campaign.py for full rationale).

No data migration needed: attempt_count defaults to 1 for any recipient
already frozen by a Phase 4A Start (none has been executed yet), and the new
attempts table starts empty.

Revision ID: 0031
Revises: 0030
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "voice_campaign_recipients",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "voice_campaign_recipient_attempts",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "recipient_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_campaign_recipients.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("execution_key", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("provider_call_id", sa.String(255), nullable=True),
        sa.Column("tts_char_count", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "execution_key", name="uq_voice_campaign_attempt_execution_key",
        ),
    )
    op.create_index(
        "ix_voice_campaign_recipient_attempts_recipient_id",
        "voice_campaign_recipient_attempts", ["recipient_id"],
    )


def downgrade() -> None:
    op.drop_table("voice_campaign_recipient_attempts")
    op.drop_column("voice_campaign_recipients", "attempt_count")
