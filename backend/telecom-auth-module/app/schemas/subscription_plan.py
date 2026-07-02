"""Subscription plan DTOs (request/response)."""
import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

_CODE_RE = re.compile(r"^[a-z0-9]([a-z0-9_-]*[a-z0-9])?$")


class _PlanMutableFields(BaseModel):
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool = True
    default_max_users: int | None = Field(default=None, ge=0)
    default_api_rate_limit: int | None = Field(default=None, ge=0)
    default_max_api_keys: int | None = Field(default=None, ge=0)
    default_monthly_sms_limit: int | None = Field(default=None, ge=0)
    default_monthly_voice_minutes: int | None = Field(default=None, ge=0)
    default_sms_enabled: bool = False
    default_voice_enabled: bool = False
    default_missed_call_enabled: bool = False
    default_freepbx_enabled: bool = False
    default_api_access_enabled: bool = False


class PlanCreate(_PlanMutableFields):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)

    @field_validator("code")
    @classmethod
    def _validate_code(cls, v: str) -> str:
        v = v.lower().strip()
        if not _CODE_RE.match(v):
            raise ValueError(
                "code must be lowercase alphanumeric with hyphens/underscores"
            )
        return v


class PlanUpdate(BaseModel):
    """All fields optional (PATCH). Code is immutable post-create."""
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    default_max_users: int | None = Field(default=None, ge=0)
    default_api_rate_limit: int | None = Field(default=None, ge=0)
    default_max_api_keys: int | None = Field(default=None, ge=0)
    default_monthly_sms_limit: int | None = Field(default=None, ge=0)
    default_monthly_voice_minutes: int | None = Field(default=None, ge=0)
    default_sms_enabled: bool | None = None
    default_voice_enabled: bool | None = None
    default_missed_call_enabled: bool | None = None
    default_freepbx_enabled: bool | None = None
    default_api_access_enabled: bool | None = None


class PlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    is_active: bool
    default_max_users: int | None
    default_api_rate_limit: int | None
    default_max_api_keys: int | None
    default_monthly_sms_limit: int | None
    default_monthly_voice_minutes: int | None
    default_sms_enabled: bool
    default_voice_enabled: bool
    default_missed_call_enabled: bool
    default_freepbx_enabled: bool
    default_api_access_enabled: bool
    created_by: uuid.UUID | None
    updated_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class PlanListItem(BaseModel):
    """List row, enriched with company usage count."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name: str
    is_active: bool
    usage_count: int = 0


class PlanFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    sort_by: str = Field(default="created_at")
    sort_dir: str = Field(default="desc", pattern="^(asc|desc)$")

    @field_validator("sort_by")
    @classmethod
    def _validate_sort(cls, v: str) -> str:
        allowed = {"created_at", "name", "code", "is_active"}
        if v not in allowed:
            raise ValueError(f"sort_by must be one of {sorted(allowed)}")
        return v
