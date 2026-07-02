"""API Key model.

Company-scoped credentials for programmatic access. The plaintext key is shown
ONCE at creation and never stored: we keep a SHA-256 hash (unique, indexed for
O(1) auth lookups) plus a short non-secret prefix for display. Revocation is a
soft flag (revoked_at) so keys stay auditable; expiry is optional.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.company import Company


class ApiKey(Base, UUIDPkMixin, TimestampMixin):
    __tablename__ = "api_keys"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Non-secret, shown in lists so a user can tell keys apart (e.g. tk_live_a1b2c3).
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # SHA-256 hex of the full key. Unique + indexed for fast auth lookups.
    key_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    usage_count: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    company: Mapped["Company"] = relationship(lazy="selectin")  # noqa: F821