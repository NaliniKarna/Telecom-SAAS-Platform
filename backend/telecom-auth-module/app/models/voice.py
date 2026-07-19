"""Voice Platform ORM models (Phase 5).

Two tables back the Voice module:

  voice_extensions   — per-company SIP/PJSIP extension registry.  Company admins
                       define which extensions exist and which user is assigned to
                       each. The agent_status field tracks real-time presence and
                       is updated by the UI / AMI events.

  voice_call_logs    — Call Detail Records (CDR).  Every originated or received
                       call gets a row here.  The status column tracks the call
                       lifecycle from "initiated" through "completed".  Inbound
                       CDRs from AMI are stubbed for now; the table is ready.

Both tables are company_id-scoped (tenant-isolated).  Neither stores AMI
credentials; those live in telephony_connections.  The AsteriskProvider seam
(app/services/asterisk_provider.py) is used for all PBX operations — services
never touch AMI directly.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class VoiceExtension(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    """A SIP/PJSIP extension registered in the platform for a company.

    Extension numbers are unique *per company* (two companies may both have
    extension 1001).  The unique constraint is defined in the migration as a
    partial index (WHERE deleted_at IS NULL) so soft-deletes don't block reuse.
    """

    __tablename__ = "voice_extensions"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "extension_number",
            name="uq_voice_ext_company_number",
        ),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The dialable number, e.g. "1001", "2200".
    extension_number: Mapped[str] = mapped_column(String(20), nullable=False)

    # Human-readable label for the extension, e.g. "Support Desk Line 1".
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Optional description / notes.
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Asterisk context, default "from-internal" (matches most FreePBX defaults).
    context: Mapped[str] = mapped_column(
        String(100), nullable=False, default="from-internal"
    )

    # SIP technology prefix used when building the channel string for Originate.
    # "PJSIP" is the modern default; legacy FreePBX setups may use "SIP".
    technology: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PJSIP"
    )

    # Whether the extension is available for use.
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Assigned user — nullable (an extension may be unassigned / a trunk).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Real-time presence: "available" | "busy" | "away" | "offline".
    # Updated by UI (manually) or AMI PresenceState events (Phase 6+).
    agent_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="offline"
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- relationships -------------------------------------------------------
    company: Mapped["Company"] = relationship(lazy="selectin")
    user: Mapped["User | None"] = relationship(
        foreign_keys=[user_id], lazy="selectin"
    )

    @property
    def channel_string(self) -> str:
        """Full AMI channel string: e.g. 'PJSIP/1001'."""
        return f"{self.technology}/{self.extension_number}"


class VoiceCallLog(Base, UUIDPkMixin, TimestampMixin):
    """Call Detail Record (CDR) for every voice call (inbound and outbound).

    This is the authoritative call history store.  The status column drives
    both the active-call view (status in ACTIVE_CALL_STATUSES and ended_at IS
    NULL) and the CDR analytics aggregations.

    Recording URL is nullable and reserved for a future recording integration.
    No soft-delete: CDRs are historical records and must not be deleted.
    """

    __tablename__ = "voice_call_logs"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Which PBX connection was used for this call.
    connection_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("telephony_connections.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # "inbound" | "outbound"
    direction: Mapped[str] = mapped_column(String(20), nullable=False)

    # Lifecycle status (see CallStatus enum in constants.py).
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="initiated", index=True
    )

    # A-leg: the caller (for outbound calls this is the agent's extension).
    caller_number: Mapped[str] = mapped_column(String(80), nullable=False)

    # B-leg: the destination / callee.
    callee_number: Mapped[str] = mapped_column(String(80), nullable=False)

    # Resolved extension FKs (nullable — a call may involve external numbers).
    caller_extension_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_extensions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    callee_extension_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("voice_extensions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Wall-clock timestamps.
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Duration (seconds) of the answered portion; NULL until the call ends.
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Time (seconds) the callee rang before answer / hangup.
    ring_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # AMI action_id returned by provider.originate() — used for event correlation.
    action_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Asterisk context used for the call.
    context: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Asterisk hangup cause string, e.g. "NORMAL_CLEARING", "BUSY".
    hangup_cause: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Reserved for future recording integration.
    recording_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # User who triggered the call (click-to-call / dialer).
    initiated_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # --- relationships -------------------------------------------------------
    company: Mapped["Company"] = relationship(lazy="selectin")
    caller_extension: Mapped["VoiceExtension | None"] = relationship(
        foreign_keys=[caller_extension_id], lazy="selectin"
    )
    callee_extension: Mapped["VoiceExtension | None"] = relationship(
        foreign_keys=[callee_extension_id], lazy="selectin"
    )
    initiator: Mapped["User | None"] = relationship(
        foreign_keys=[initiated_by], lazy="selectin"
    )
