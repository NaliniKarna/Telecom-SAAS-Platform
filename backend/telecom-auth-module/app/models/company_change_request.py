"""Company change request (approval workflow for gated settings fields)."""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ChangeRequestStatus
from app.db.base import Base, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


class CompanyChangeRequest(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "company_change_requests"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[ChangeRequestStatus] = mapped_column(
        SAEnum(
            ChangeRequestStatus,
            name="change_request_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=ChangeRequestStatus.PENDING,
        nullable=False,
        index=True,
    )
    # Per-field diff: { "name": {"old": "...", "new": "..."}, ... }
    changes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    company: Mapped["Company"] = relationship(lazy="selectin")  # noqa: F821
    requester: Mapped["User | None"] = relationship(  # noqa: F821
        foreign_keys=[requested_by], lazy="selectin"
    )
