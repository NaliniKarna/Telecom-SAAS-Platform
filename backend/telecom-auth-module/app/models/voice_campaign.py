"""Voice Campaign Foundation + TTS Usage Metering models (Phase 4A).

Five entities:

  TtsUsage              — one row per (company, calendar month). The
                           monthly ceiling accounting lives here:
                           consumed_characters + reserved_characters is
                           checked against subscription_plan.default_
                           monthly_tts_characters (NULL = unlimited, 0 =
                           no TTS at all). Never manually reset — a new
                           month is a new row, created lazily on first use.

  TtsUsageReservation    — one row per reserved "slice" of a month's quota,
                           keyed by (reference_type, reference_id) so the
                           same logical action (a campaign Start, a TTS
                           preview generation) can never reserve twice —
                           the unique constraint is the DB-level backstop
                           for the idempotency the service layer already
                           implements. reserved_characters is the amount
                           carved out of TtsUsage.reserved_characters;
                           consumed_characters tracks how much of that
                           slice has actually been converted to real usage
                           so far (see app.services.tts_usage_service for
                           the reserve -> consume/release state machine).

  VoiceCampaign          — the campaign itself. DRAFT is fully mutable
                           (contact list / template / voice selection can
                           all change); Start() (see
                           app.services.voice_campaign_service) is the one
                           transaction that freezes everything below into
                           an immutable execution snapshot and flips status
                           to PROCESSING. resolved_voice_id is that
                           snapshot's voice — separate from voice_id (the
                           mutable pre-start selection/override) so a later
                           change to the template's voice, or to the
                           campaign's own voice override, can never alter a
                           campaign that has already started.

  VoiceCampaignRecipient — one row per resolved contact, frozen at Start.
                           variables/rendered_text/tts_char_count are all
                           computed once at Start and never recomputed —
                           a later Contact or Voice Template edit must not
                           change a started campaign's history (spec
                           requirement). correlation_id is deterministic
                           (uuid5 of campaign_id + phone) so a retried
                           Start (blocked by the campaign-row lock/status
                           guard anyway) or a future Phase 4B retry can
                           always re-derive the same id instead of minting
                           a new one.

  VoiceCampaignAudio     — deliberately a SEPARATE table from TtsPreview
                           (spec requirement 6: "must be separate from
                           temporary TtsPreview audio"). Phase 4A never
                           inserts a row here — no TTS is generated at
                           Start — but the table/FKs exist now so Phase 4B
                           has a durable place to point future-generated
                           audio at, without a schema change. pbx_reachable
                           defaults False on purpose: a local FileStorage
                           URL is not something a client's remote
                           FreePBX/Asterisk box can necessarily fetch (spec
                           section 6) — Phase 4B must consciously flip this
                           once a real handoff mechanism exists, rather
                           than the schema silently implying "yes, PBX can
                           already read this".
"""
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.company import Company


# =========================================================================== #
# TTS Usage Metering
# =========================================================================== #
class TtsUsage(Base, UUIDPkMixin, TimestampMixin):
    """One row per (company, calendar month). usage_month is always the
    first day of that month (UTC) — see app.services.tts_usage_service.
    current_usage_month(). Monthly separation falls out of the unique
    constraint; no reset job is needed."""

    __tablename__ = "tts_usage"
    __table_args__ = (
        UniqueConstraint("company_id", "usage_month", name="uq_tts_usage_company_month"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    usage_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    consumed_characters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_characters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Optional metadata (spec: "optional request/count metadata if useful") —
    # total number of reserve() calls this month, for observability only;
    # nothing in the quota check reads this.
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TtsUsageReservation(Base, UUIDPkMixin, TimestampMixin):
    """One reservation per (reference_type, reference_id) — the unique
    constraint makes reserve() safe to call twice for the same logical
    action (a campaign Start, a TTS preview) without double-reserving.

    reference_type / reference_id are a deliberately generic polymorphic
    pointer (not a FK) — Phase 4A only ever writes "voice_campaign" (one
    reservation per campaign, sized to the whole Start-time estimate) and
    "tts_preview" (one reservation per preview generation), but the shape
    already supports a future finer-grained "voice_campaign_recipient"
    reference if Phase 4B decides to split a campaign's reservation into
    per-recipient slices — see the module docstring and the Phase 4B note
    in IMPLEMENTATION-REPORT.md."""

    __tablename__ = "tts_usage_reservations"
    __table_args__ = (
        UniqueConstraint(
            "reference_type", "reference_id",
            name="uq_tts_reservation_reference",
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    usage_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reference_type: Mapped[str] = mapped_column(String(40), nullable=False)
    reference_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    reserved_characters: Mapped[int] = mapped_column(Integer, nullable=False)
    consumed_characters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")


# =========================================================================== #
# Voice Campaigns
# =========================================================================== #
class VoiceCampaign(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "voice_campaigns"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- draft-time selection (mutable while status == draft) -------------
    contact_list_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("contact_lists.id", ondelete="SET NULL"),
        nullable=True,
    )
    voice_template_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Optional per-campaign voice override, same idea as TtsPreviewRequest.
    # voice_id — defaults to the template's own voice when NULL.
    voice_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ai_voices.id", ondelete="SET NULL"),
        nullable=True,
    )

    # --- immutable execution snapshot (written once, by Start) -------------
    resolved_voice_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ai_voices.id", ondelete="RESTRICT"),
        nullable=True,
    )
    reservation_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tts_usage_reservations.id", ondelete="SET NULL"),
        nullable=True,
    )
    total_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_tts_characters: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)
    # Informational only in Phase 4A — no scheduler/worker reads this yet;
    # recorded so the existing SMS-style schedule/send split is available to
    # Phase 4B without another migration.
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    recipients: Mapped[list["VoiceCampaignRecipient"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", lazy="noload",
    )


class VoiceCampaignRecipient(Base, UUIDPkMixin, TimestampMixin):
    """Frozen at Start; never recomputed from live Contact/Template data
    afterward (spec requirement — see module docstring)."""

    __tablename__ = "voice_campaign_recipients"
    __table_args__ = (
        UniqueConstraint("correlation_id", name="uq_voice_campaign_recipient_correlation"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Soft link for traceability only — the columns below are the source of
    # truth once frozen, exactly like SmsCampaignRecipient.contact_id.
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    phone_e164: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    resolved_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Snapshot of the exact values used to render this recipient's text —
    # kept even though rendered_text is also stored, so a rendering dispute
    # can be reproduced/debugged later (spec requirement 5).
    variables: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rendered_text: Mapped[str] = mapped_column(String(4000), nullable=False)
    tts_char_count: Mapped[int] = mapped_column(Integer, nullable=False)

    audio_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_campaign_audios.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", index=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Deterministic idempotency/correlation id — uuid5(campaign_id, phone),
    # see app.services.voice_campaign_service._correlation_id(). Stable across
    # every attempt this recipient ever gets (identifies the RECIPIENT, not
    # one execution of it — see attempt_count/VoiceCampaignRecipientAttempt
    # for per-attempt identity).
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # Phase 4B: how many execution attempts this recipient has had, starting
    # at 1 once Start publishes its first Kafka event. Combined with
    # recipient.id this derives each attempt's own execution_key (see
    # app.workers.voice_campaign_worker._execution_key) — bumped only by an
    # explicit manual retry (POST .../retry), never by the worker itself, so
    # Kafka's own at-least-once redelivery of the SAME attempt is caught by
    # VoiceCampaignRecipientAttempt's unique execution_key instead of minting
    # a new attempt.
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    campaign: Mapped["VoiceCampaign"] = relationship(back_populates="recipients")


class VoiceCampaignAudio(Base, UUIDPkMixin, TimestampMixin):
    """Durable campaign-audio reference. Separate table from TtsPreview by
    design (spec requirement 6). No Phase 4A code path inserts a row here —
    see module docstring — this exists purely as the seam Phase 4B writes
    into once it actually calls the TTS provider per recipient."""

    __tablename__ = "voice_campaign_audios"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_campaign_recipients.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    storage_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Where storage_url actually lives — "local" (today's FileStorage
    # backend) vs a future object-store backend. Not read by anything yet;
    # recorded so a future retention/cleanup policy and the PBX handoff
    # mechanism (see pbx_reachable) both have something to key off.
    storage_backend: Mapped[str] = mapped_column(String(50), nullable=False, default="local")
    # False until a future handoff mechanism confirms the client's
    # FreePBX/Asterisk box can actually fetch storage_url (spec section 6 —
    # deliberately NOT solved in Phase 4A).
    pbx_reachable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class VoiceCampaignRecipientAttempt(Base, UUIDPkMixin, TimestampMixin):
    """Phase 4B: one row per execution attempt of a recipient.

    Deliberately a separate small entity rather than overwriting the only
    result fields on VoiceCampaignRecipient (spec requirement — "introduce a
    small call-attempt entity rather than overwriting the only result
    fields"). The recipient row always reflects its LATEST/current status;
    this table preserves the history of every attempt that led there,
    including ones superseded by a manual retry.

    execution_key is the durable idempotency anchor for one attempt: a
    deterministic uuid5 of (recipient_id, attempt_number) — see
    app.workers.voice_campaign_worker._execution_key(). The unique
    constraint is what lets Kafka's at-least-once redelivery of the exact
    same event resolve to "already claimed, no-op" instead of a second
    execution, independent of (and in addition to) the in-memory dedup
    PlatformConsumer already does — that cache is per-process and reset on
    restart; this table is the durable, cross-restart, cross-worker-instance
    backstop, mirroring TtsUsageReservation's own (reference_type,
    reference_id) uniqueness pattern from Phase 4A.
    """

    __tablename__ = "voice_campaign_recipient_attempts"
    __table_args__ = (
        UniqueConstraint("execution_key", name="uq_voice_campaign_attempt_execution_key"),
    )

    recipient_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_campaign_recipients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_key: Mapped[str] = mapped_column(String(64), nullable=False)

    # Reuses VoiceCampaignRecipientStatus values — this attempt's own
    # progress, independent of whatever the parent recipient row currently
    # shows (relevant once a later attempt supersedes this one).
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing")
    provider_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tts_char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
