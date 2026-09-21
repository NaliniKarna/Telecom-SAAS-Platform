"""AI Voice / TTS foundation models.

Three entities, deliberately minimal for this phase (see module docstrings
in app/services/tts_service.py and app/services/ai_voice_service.py for the
full architecture rationale):

  AiVoice       — the voice library. Platform-wide catalog (company_id is
                  nullable: NULL = available to every tenant). Nothing here
                  implements voice cloning/training; provider_voice_id is
                  just an opaque id the configured TTS provider understands.

  VoiceTemplate — tenant-scoped. {{variable}} text + a selected voice.
                  Mirrors SmsTemplate's shape (name/body/variables/status/
                  soft-delete) so the two feel like siblings in the codebase.

  TtsPreview    — one durable row per "Generate TTS" action. This is the
                  "stable audio reference" the spec asks for: a preview
                  generates audio, stores it via the existing FileStorage
                  abstraction, and records the resulting URL here so the
                  frontend (and, later, a Voice Campaign worker) has
                  something durable to point at instead of an ephemeral
                  response body. NOT a campaign, NOT a queued message —
                  purely a record of "this text, with this voice, produced
                  this audio file."
"""
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin


class AiVoice(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "ai_voices"

    # NULL = platform-wide voice, visible to every company. A non-NULL value
    # is reserved for a future "custom/company voice" capability (explicitly
    # out of scope this phase) — the column exists now so that feature won't
    # need a schema change later, per the spec's "allow custom/company voices
    # later without redesigning" requirement.
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_voice_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class VoiceTemplate(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "voice_templates"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(String(4000), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    voice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ai_voices.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    variables: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class TtsPreview(Base, UUIDPkMixin, TimestampMixin):
    """One durable record per TTS preview generation. Never becomes a
    campaign/message/call — see module docstring."""

    __tablename__ = "tts_previews"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    voice_template_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    voice_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ai_voices.id", ondelete="RESTRICT"),
        nullable=False,
    )
    rendered_text: Mapped[str] = mapped_column(String(4000), nullable=False)
    audio_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
