"""Telephony connection model (FreePBX / Asterisk integration layer).

Hybrid topology: one row with company_id IS NULL is the shared PLATFORM-DEFAULT
connection; a row with a company_id is that tenant's OVERRIDE. The effective
connection for a company is its own enabled row if present, else the platform
default (resolution lives in the repository).

The AMI secret is encrypted at rest (app/core/crypto.py) — the column holds an
opaque Fernet token, never plaintext, and the secret is never serialized back
out (schemas expose only `secret_set: bool`).
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import TelephonyConnectionStatus
from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.company import Company


class TelephonyConnection(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "telephony_connections"

    # NULL => platform-default (shared) connection; set => per-tenant override.
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # --- Asterisk Manager Interface (AMI) connection params ---
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False, default=5038)
    ami_username: Mapped[str] = mapped_column(String(255), nullable=False)
    # Fernet-encrypted AMI secret (opaque token). Never plaintext, never serialized.
    ami_secret_encrypted: Mapped[str] = mapped_column(String(1000), nullable=False)
    use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Whether this connection is eligible to be used / tested.
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Last-known reachability, refreshed by a status test (string-valued enum,
    # matching the project's enum-as-varchar convention).
    last_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TelephonyConnectionStatus.UNKNOWN.value
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Free-form room for future fields (ARI base url, SIP trunk hints, etc.)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    company: Mapped["Company | None"] = relationship(lazy="selectin")  # noqa: F821
