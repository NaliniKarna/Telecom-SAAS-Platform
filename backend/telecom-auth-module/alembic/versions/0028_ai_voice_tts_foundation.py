"""ai voice tts foundation

Adds the AI Voice TTS foundation: a platform-wide voice library
(ai_voices), tenant-scoped Voice Templates (voice_templates), and a durable
record of each TTS preview generation (tts_previews) — the "stable audio
reference" the spec calls for. Also adds the AI Voice entitlement gate to
subscription_plans and companies, mirroring the existing sms/voice/
missed_call/freepbx enabled-flag pattern (see those columns in the same two
tables for precedent).

Seeds one default voice row carried over from the nepali-tts reference
project (ElevenLabs, eleven_multilingual_v2, voice id cgSgspJ2msm6clMCkdW9)
so the Voice Library isn't empty on a fresh install.

Revision ID: 0028
Revises: 0027
"""
import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

_SEED_VOICE_ID = "b2a1c9d0-6e3f-4a11-9c2e-8f7d5a0b1e4c"


def upgrade() -> None:
    op.create_table(
        "ai_voices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_voice_id", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_ai_voices_company_id", "ai_voices", ["company_id"])
    op.create_index("ix_ai_voices_status", "ai_voices", ["status"])

    op.create_table(
        "voice_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("text", sa.String(4000), nullable=False),
        sa.Column("language", sa.String(20), nullable=False),
        sa.Column(
            "voice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_voices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("variables", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_voice_templates_company_id", "voice_templates", ["company_id"])
    op.create_index("ix_voice_templates_voice_id", "voice_templates", ["voice_id"])
    op.create_index("ix_voice_templates_status", "voice_templates", ["status"])

    op.create_table(
        "tts_previews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "voice_template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "voice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ai_voices.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rendered_text", sa.String(4000), nullable=False),
        sa.Column("audio_url", sa.String(1000), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("char_count", sa.Integer(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_tts_previews_company_id", "tts_previews", ["company_id"])
    op.create_index("ix_tts_previews_voice_template_id", "tts_previews", ["voice_template_id"])

    op.add_column(
        "subscription_plans",
        sa.Column("default_ai_voice_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "companies",
        sa.Column("ai_voice_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.execute(
        f"""
        INSERT INTO ai_voices
            (id, company_id, name, language, gender, description, provider, provider_voice_id, status)
        VALUES
            ('{_SEED_VOICE_ID}', NULL, 'Nepali Voice 1', 'ne', NULL,
             'Default Nepali-capable ElevenLabs voice, carried over from the nepali-tts reference project.',
             'elevenlabs', 'cgSgspJ2msm6clMCkdW9', 'active')
        """
    )


def downgrade() -> None:
    op.drop_column("companies", "ai_voice_enabled")
    op.drop_column("subscription_plans", "default_ai_voice_enabled")
    op.drop_index("ix_tts_previews_voice_template_id", "tts_previews")
    op.drop_index("ix_tts_previews_company_id", "tts_previews")
    op.drop_table("tts_previews")
    op.drop_index("ix_voice_templates_status", "voice_templates")
    op.drop_index("ix_voice_templates_voice_id", "voice_templates")
    op.drop_index("ix_voice_templates_company_id", "voice_templates")
    op.drop_table("voice_templates")
    op.drop_index("ix_ai_voices_status", "ai_voices")
    op.drop_index("ix_ai_voices_company_id", "ai_voices")
    op.drop_table("ai_voices")
