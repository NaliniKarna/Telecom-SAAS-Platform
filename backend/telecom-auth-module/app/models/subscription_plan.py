"""Subscription plan reference table.

Platform-level catalog (not tenant-scoped). A company references a plan via
plan_id; the plan carries default limits/entitlements that a company may
override at the company level. Seeded with the baseline tiers.

Extended for the Super Admin plan-management module: description, additional
limits (api keys, monthly sms/voice), api access flag, and created_by/updated_by
attribution. Soft-deletable so plans can be retired without breaking historical
company references.
"""
import uuid

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin


class SubscriptionPlan(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "subscription_plans"

    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Default limits (NULL = unlimited). Companies may override per-tenant.
    default_max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_api_rate_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    default_max_api_keys: Mapped[int | None] = mapped_column(Integer, nullable=True)
    default_monthly_sms_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    default_monthly_voice_minutes: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    # Default module entitlements granted by this plan.
    default_sms_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    default_voice_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    default_missed_call_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    default_freepbx_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    default_api_access_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Attribution (nullable: seed/system rows and pre-existing plans have none).
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), nullable=True
    )