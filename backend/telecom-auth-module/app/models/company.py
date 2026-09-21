"""Company (tenant root) model."""
import uuid

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer
from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import CompanyStatus
from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.subscription_plan import SubscriptionPlan
    from app.models.user import User


class Company(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    status: Mapped[CompanyStatus] = mapped_column(
        SAEnum(
            CompanyStatus,
            name="company_status",
            values_callable=lambda e: [m.value for m in e],
        ),
        default=CompanyStatus.ACTIVE,
        nullable=False,
    )

    # Subscription plan reference (replaces the old free-text `plan` string).
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # --- contact information ---
    contact_email: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # --- profile / branding (editable by the company admin) ---
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # --- per-tenant module entitlements (override plan defaults) ---
    sms_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    voice_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    missed_call_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    freepbx_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # AI Voice / TTS foundation entitlement (Voices, Voice Templates, TTS
    # preview). Mirrors the sms_enabled/voice_enabled override pattern above;
    # not yet enforced by usage-limit fields — see SubscriptionPlan for why.
    ai_voice_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # --- per-tenant limits (NULL = unlimited / inherit) ---
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    api_rate_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)

    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )

    users: Mapped[list["User"]] = relationship(  # noqa: F821
        back_populates="company", cascade="all, delete-orphan"
    )
    plan: Mapped["SubscriptionPlan | None"] = relationship(  # noqa: F821
        lazy="selectin"
    )

    @property
    def is_active(self) -> bool:
        return self.status == CompanyStatus.ACTIVE
