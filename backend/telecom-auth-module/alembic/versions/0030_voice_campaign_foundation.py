"""voice campaign foundation + tts usage metering (Phase 4A)

Adds:

  tts_usage               — one row per (company, calendar month): the
                             monthly TTS-character ceiling accounting.
  tts_usage_reservations  — one row per reserved slice, keyed uniquely by
                             (reference_type, reference_id) so a reserve()
                             call is idempotent at the DB level, not just
                             in the service layer.
  voice_campaigns / voice_campaign_recipients / voice_campaign_audios —
                             the Voice Campaign foundation itself. See
                             app/models/voice_campaign.py for the full
                             rationale of every column; this migration
                             mirrors that file exactly.

No data migration/backfill needed — these are all brand-new tables with
no pre-existing rows anywhere.

Revision ID: 0030
Revises: 0029
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- TTS usage metering -------------------------------------------------
    op.create_table(
        "tts_usage",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("usage_month", sa.Date(), nullable=False),
        sa.Column("consumed_characters", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_characters", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "usage_month", name="uq_tts_usage_company_month"),
    )
    op.create_index("ix_tts_usage_company_id", "tts_usage", ["company_id"])
    op.create_index("ix_tts_usage_usage_month", "tts_usage", ["usage_month"])

    op.create_table(
        "tts_usage_reservations",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("usage_month", sa.Date(), nullable=False),
        sa.Column("reference_type", sa.String(40), nullable=False),
        sa.Column("reference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reserved_characters", sa.Integer(), nullable=False),
        sa.Column("consumed_characters", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "reference_type", "reference_id", name="uq_tts_reservation_reference",
        ),
    )
    op.create_index("ix_tts_usage_reservations_company_id", "tts_usage_reservations", ["company_id"])
    op.create_index("ix_tts_usage_reservations_usage_month", "tts_usage_reservations", ["usage_month"])

    # --- Voice campaigns -----------------------------------------------------
    op.create_table(
        "voice_campaigns",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "contact_list_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contact_lists.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "voice_template_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_templates.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "voice_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_voices.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "resolved_voice_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_voices.id", ondelete="RESTRICT"), nullable=True,
        ),
        sa.Column(
            "reservation_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tts_usage_reservations.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("total_recipients", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_tts_characters", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_index("ix_voice_campaigns_company_id", "voice_campaigns", ["company_id"])
    op.create_index("ix_voice_campaigns_status", "voice_campaigns", ["status"])
    op.create_index(
        "ix_voice_campaigns_company_status", "voice_campaigns", ["company_id", "status"],
    )

    # --- Campaign-generated audio (separate from tts_previews) --------------
    # Created before voice_campaign_recipients so the recipient table's FK to
    # it can be added; the recipient -> audio FK is nullable (no audio exists
    # in Phase 4A), so table creation order here has no data dependency.
    op.create_table(
        "voice_campaign_audios",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "campaign_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_campaigns.id", ondelete="CASCADE"), nullable=False,
        ),
        # FK to voice_campaign_recipients added after that table exists below.
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_url", sa.String(1000), nullable=False),
        sa.Column("content_type", sa.String(50), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("storage_backend", sa.String(50), nullable=False, server_default="local"),
        sa.Column("pbx_reachable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("recipient_id", name="uq_voice_campaign_audio_recipient"),
    )
    op.create_index("ix_voice_campaign_audios_company_id", "voice_campaign_audios", ["company_id"])
    op.create_index("ix_voice_campaign_audios_campaign_id", "voice_campaign_audios", ["campaign_id"])

    # --- Campaign recipients (frozen execution snapshot) --------------------
    op.create_table(
        "voice_campaign_recipients",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"), primary_key=True,
        ),
        sa.Column(
            "campaign_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_campaigns.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "contact_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("phone_e164", sa.String(20), nullable=False),
        sa.Column("resolved_name", sa.String(255), nullable=True),
        sa.Column("variables", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("rendered_text", sa.String(4000), nullable=False),
        sa.Column("tts_char_count", sa.Integer(), nullable=False),
        sa.Column(
            "audio_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_campaign_audios.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "correlation_id", name="uq_voice_campaign_recipient_correlation",
        ),
    )
    op.create_index(
        "ix_voice_campaign_recipients_campaign_id", "voice_campaign_recipients", ["campaign_id"],
    )
    op.create_index(
        "ix_voice_campaign_recipients_phone_e164", "voice_campaign_recipients", ["phone_e164"],
    )
    op.create_index(
        "ix_voice_campaign_recipients_status", "voice_campaign_recipients", ["status"],
    )

    op.create_foreign_key(
        "fk_voice_campaign_audios_recipient",
        "voice_campaign_audios", "voice_campaign_recipients",
        ["recipient_id"], ["id"], ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_voice_campaign_audios_recipient", "voice_campaign_audios", type_="foreignkey",
    )
    op.drop_table("voice_campaign_recipients")
    op.drop_table("voice_campaign_audios")
    op.drop_table("voice_campaigns")
    op.drop_table("tts_usage_reservations")
    op.drop_table("tts_usage")
