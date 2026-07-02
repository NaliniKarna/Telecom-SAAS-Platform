"""Company DTOs: separate request and response models."""
import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.constants import CompanyStatus

_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")


# --- subscription plan (read-only reference) -------------------------------
class SubscriptionPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    is_active: bool
    default_max_users: int | None
    default_api_rate_limit: int | None
    default_sms_enabled: bool
    default_voice_enabled: bool
    default_missed_call_enabled: bool
    default_freepbx_enabled: bool


# --- shared entitlement / limit fields -------------------------------------
class _CompanyMutableFields(BaseModel):
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=30)
    sms_enabled: bool | None = None
    voice_enabled: bool | None = None
    missed_call_enabled: bool | None = None
    freepbx_enabled: bool | None = None
    max_users: int | None = Field(default=None, ge=0)
    api_rate_limit: int | None = Field(default=None, ge=0)


class CompanyCreate(_CompanyMutableFields):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=100)
    plan_id: uuid.UUID | None = None

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        v = v.lower()
        if not _SLUG_RE.match(v):
            raise ValueError(
                "slug must be lowercase alphanumeric with hyphens, "
                "not starting or ending with a hyphen"
            )
        return v


class CompanyUpdate(_CompanyMutableFields):
    """All fields optional — PATCH semantics. Slug is immutable post-create."""
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    plan_id: uuid.UUID | None = None


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    status: CompanyStatus
    plan_id: uuid.UUID | None
    plan: SubscriptionPlanRead | None = None
    contact_email: str | None
    contact_phone: str | None
    address: str | None = None
    timezone: str | None = None
    logo_url: str | None = None
    sms_enabled: bool
    voice_enabled: bool
    missed_call_enabled: bool
    freepbx_enabled: bool
    max_users: int | None
    api_rate_limit: int | None
    created_at: datetime
    updated_at: datetime


class CompanyListPlanRef(BaseModel):
    """Minimal plan reference for list rows (name only — the full plan DTO is
    intentionally not used here to keep list payloads light)."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class CompanyListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    slug: str
    status: CompanyStatus
    plan_id: uuid.UUID | None
    # Eager-loaded via the Company.plan relationship (lazy="selectin"), so this
    # is populated for the whole page in one extra query — no N+1.
    plan: CompanyListPlanRef | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    created_at: datetime


class CompanyFilter(BaseModel):
    """Query parameters for listing companies: search, status, plan, sorting."""
    model_config = ConfigDict(extra="forbid")
    search: str | None = Field(default=None, max_length=255)
    status: CompanyStatus | None = None
    plan_id: uuid.UUID | None = None
    sort_by: str = Field(default="created_at")
    sort_dir: str = Field(default="desc", pattern="^(asc|desc)$")

    @field_validator("sort_by")
    @classmethod
    def _validate_sort(cls, v: str) -> str:
        allowed = {"created_at", "name", "slug", "status"}
        if v not in allowed:
            raise ValueError(f"sort_by must be one of {sorted(allowed)}")
        return v


# --- Company Settings (Company Admin, self-scoped) -------------------------
# What a company admin may edit about their OWN company. Deliberately excludes
# plan/limits/feature-entitlements/status — those are platform-controlled and
# returned read-only. There is no company id here; the service always uses the
# caller's own company from the token.
class CompanySettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=500)
    timezone: str | None = Field(default=None, max_length=64)
    logo_url: str | None = Field(default=None, max_length=1000)


class CompanySettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    # Editable
    id: uuid.UUID
    name: str
    contact_email: str | None
    contact_phone: str | None
    address: str | None
    timezone: str | None
    logo_url: str | None
    # Read-only (platform-controlled)
    slug: str
    status: CompanyStatus
    plan: SubscriptionPlanRead | None = None
    max_users: int | None
    api_rate_limit: int | None
    sms_enabled: bool
    voice_enabled: bool
    missed_call_enabled: bool
    freepbx_enabled: bool
    created_at: datetime
    updated_at: datetime