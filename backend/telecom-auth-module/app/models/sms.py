"""SQLAlchemy models for the SMS module.

Foundation scope is Sender IDs + Templates. The Campaign / CampaignRecipient /
Message models below back tables that already exist in the database
(migrations 0015-0017); they are retained so the schema and ORM stay in sync,
but no Foundation service/route references them yet (Campaigns/Sending is a
later module).

Enum-typed columns are stored as String to match the migrations (which use
sa.String, not native PG enums). The Python enums are still used in the app
layer for type-safety; values are persisted/read as their string values.
"""
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
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class SmsSenderId(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sms_sender_ids"
    # Sender ID strings are unique PER COMPANY, never globally — two tenants may
    # legitimately register the same alphanumeric sender.
    __table_args__ = (
        UniqueConstraint("company_id", "sender_id", name="uq_sms_sender_company_value"),
    )

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_id: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    approval_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    company: Mapped["Company"] = relationship(lazy="selectin")
    reviewer: Mapped["User | None"] = relationship(foreign_keys=[reviewed_by], lazy="selectin")


class SmsTemplate(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sms_templates"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(String(4000), nullable=False)
    variables: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class SmsCampaign(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    """Backs the existing sms_campaigns table (migration 0015). Not used by the
    Foundation; present so the ORM matches the DB."""
    __tablename__ = "sms_campaigns"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sms_sender_ids.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sms_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="contacts")
    source_list_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("contact_lists.id", ondelete="SET NULL"),
        nullable=True,
    )
    schedule_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delivered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class SmsCampaignRecipient(Base, UUIDPkMixin, TimestampMixin):
    """Backs the existing sms_campaign_recipients table (migration 0016)."""
    __tablename__ = "sms_campaign_recipients"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sms_campaigns.id", ondelete="CASCADE"),
        nullable=False,
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    phone_e164: Mapped[str] = mapped_column(String(20), nullable=False)
    resolved_name: Mapped[str | None] = mapped_column(String(255), nullable=True)


class SmsMessage(Base, UUIDPkMixin, TimestampMixin):
    """Backs the existing sms_messages table (migration 0017)."""
    __tablename__ = "sms_messages"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sms_campaigns.id", ondelete="SET NULL"),
        nullable=True,
    )
    recipient_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    sender_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    content: Mapped[str] = mapped_column(String(4000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    error_details: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
