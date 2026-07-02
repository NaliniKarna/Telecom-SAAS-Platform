"""Platform settings model.

Single-row table holding global platform configuration: general info, default
limits applied to new companies, module feature toggles, and security policy.
A fixed singleton id keeps it to exactly one row (upserted, never multiplied).
"""
import uuid

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

# Fixed primary key for the single settings row.
SETTINGS_SINGLETON_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class PlatformSettings(Base, TimestampMixin):
    __tablename__ = "platform_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=SETTINGS_SINGLETON_ID
    )

    # General
    platform_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="Telecom Platform"
    )
    platform_logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    support_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    support_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Defaults applied to new companies
    default_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    default_user_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_api_key_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    default_api_rate_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # Feature toggles (platform-wide module availability)
    sms_module_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    voice_module_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    missed_call_module_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    api_access_module_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    # Security
    jwt_expiry_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=15
    )
    password_min_length: Mapped[int] = mapped_column(
        Integer, nullable=False, default=8
    )
    password_require_uppercase: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    password_require_number: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    password_require_symbol: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
