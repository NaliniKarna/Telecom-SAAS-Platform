"""Contact, ContactList, ContactListMember models.

Company-scoped contacts (people you message — distinct from platform users).
Numbers are stored both raw (as typed) and normalized to E.164. Tags are
free-form strings (JSONB array). Lists are dedicated tables (not the user-group
tables); membership FKs to contacts, never users.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ContactNumberType, ContactStatus
from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.company import Company


class Contact(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "contacts"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Numbers: raw (as typed) + E.164 normalized. e164 columns are indexed for
    # duplicate detection and future message routing.
    mobile_raw: Mapped[str | None] = mapped_column(String(40), nullable=True)
    mobile_e164: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    landline_raw: Mapped[str | None] = mapped_column(String(40), nullable=True)
    landline_e164: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    number_type: Mapped[ContactNumberType] = mapped_column(
        SAEnum(ContactNumberType, name="contact_number_type",
               values_callable=lambda e: [m.value for m in e]),
        default=ContactNumberType.UNKNOWN, nullable=False,
    )

    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    tags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[ContactStatus] = mapped_column(
        SAEnum(ContactStatus, name="contact_status",
               values_callable=lambda e: [m.value for m in e]),
        default=ContactStatus.ACTIVE, nullable=False, index=True,
    )

    memberships: Mapped[list["ContactListMember"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan", lazy="selectin",
    )


class ContactList(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "contact_lists"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    members: Mapped[list["ContactListMember"]] = relationship(
        back_populates="contact_list", cascade="all, delete-orphan", lazy="selectin",
    )


class ContactListMember(Base, UUIDPkMixin):
    __tablename__ = "contact_list_members"
    __table_args__ = (
        UniqueConstraint("list_id", "contact_id", name="uq_contact_list_member"),
    )

    list_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("contact_lists.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(),
    )

    contact_list: Mapped["ContactList"] = relationship(back_populates="members")
    contact: Mapped["Contact"] = relationship(back_populates="memberships")
