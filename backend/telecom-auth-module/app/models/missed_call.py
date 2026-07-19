"""Missed Call Platform ORM models (Phase 6).

Three tables:

  missed_calls           — The master missed-call log.  Each row represents a
                           single inbound call that went unanswered.  Detected
                           by the provider (AMI event or manual API) and tracked
                           through a four-state lifecycle:
                           new → acknowledged → returned → closed.

  missed_call_notes      — Timestamped notes attached to a missed call by any
                           company user (audit trail, context for callbacks).

  missed_call_callbacks  — Each callback attempt against a missed call.  Tracks
                           the voice call used, outcome, duration, and notes.
                           Reuses VoiceCallLog FK for the actual call record
                           (the callback is originated through VoiceService).

All tables are company_id-scoped (tenant-isolated).  No soft-delete on notes
or callbacks — they are append-only audit artifacts.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User
    from app.models.voice import VoiceCallLog, VoiceExtension


class MissedCall(Base, UUIDPkMixin, TimestampMixin):
    """An inbound call that was not answered.

    The status column drives the dashboard widgets and the filtered list views.
    assigned_to allows routing to a specific user for follow-up.
    """

    __tablename__ = "missed_calls"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The number that called (external caller).
    caller_number: Mapped[str] = mapped_column(String(80), nullable=False)

    # The extension / number that was supposed to receive the call.
    called_number: Mapped[str] = mapped_column(String(80), nullable=False)

    # The extension that was being rung (nullable — may be an external number).
    called_extension_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_extensions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Lifecycle: new → acknowledged → returned → closed
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="new", index=True
    )

    # When the call came in.
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # How long it rang before being missed (seconds).
    ring_duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # FK to the original voice_call_logs row (if the inbound CDR was recorded).
    source_call_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_call_logs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Assignment: which user is responsible for calling back.
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Number of callback attempts made for this missed call.
    callback_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    # Caller ID label (if resolved from contacts or AMI).
    caller_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # ── relationships ────────────────────────────────────────────────────────
    company: Mapped["Company"] = relationship(lazy="selectin")
    called_extension: Mapped["VoiceExtension | None"] = relationship(
        foreign_keys=[called_extension_id], lazy="selectin"
    )
    assignee: Mapped["User | None"] = relationship(
        foreign_keys=[assigned_to], lazy="selectin"
    )
    notes: Mapped[list["MissedCallNote"]] = relationship(
        back_populates="missed_call",
        order_by="MissedCallNote.created_at.asc()",
        lazy="selectin",
    )
    callbacks: Mapped[list["MissedCallCallback"]] = relationship(
        back_populates="missed_call",
        order_by="MissedCallCallback.created_at.desc()",
        lazy="selectin",
    )


class MissedCallNote(Base, UUIDPkMixin, TimestampMixin):
    """A timestamped note attached to a missed call (append-only)."""

    __tablename__ = "missed_call_notes"

    missed_call_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("missed_calls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # ── relationships ────────────────────────────────────────────────────────
    missed_call: Mapped["MissedCall"] = relationship(back_populates="notes")
    author: Mapped["User"] = relationship(
        foreign_keys=[author_id], lazy="selectin"
    )


class MissedCallCallback(Base, UUIDPkMixin, TimestampMixin):
    """A single callback attempt against a missed call.

    When a user clicks "Call Back", the system originates a call via
    VoiceService.originate_call() and records the voice_call_log FK here.
    The outcome is updated when the call completes (or manually by the user).
    """

    __tablename__ = "missed_call_callbacks"

    missed_call_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("missed_calls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Who performed the callback.
    performed_by: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )

    # The extension used for the callback (nullable — may use trunk).
    extension_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_extensions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # FK to the voice CDR created by the originate.
    voice_call_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_call_logs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Outcome: answered | no_answer | busy | voicemail | failed
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Talk time (seconds); set when outcome = answered.
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Free-text note about this specific attempt.
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # When the callback was attempted.
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # ── relationships ────────────────────────────────────────────────────────
    missed_call: Mapped["MissedCall"] = relationship(back_populates="callbacks")
    performer: Mapped["User"] = relationship(
        foreign_keys=[performed_by], lazy="selectin"
    )
    extension: Mapped["VoiceExtension | None"] = relationship(
        foreign_keys=[extension_id], lazy="selectin"
    )
