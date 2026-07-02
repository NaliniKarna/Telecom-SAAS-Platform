"""Platform settings DTOs."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class PlatformSettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    platform_name: str
    platform_logo_url: str | None
    support_email: str | None
    support_phone: str | None
    default_plan_id: uuid.UUID | None
    default_user_limit: int | None
    default_api_key_limit: int | None
    default_api_rate_limit: int | None
    sms_module_enabled: bool
    voice_module_enabled: bool
    missed_call_module_enabled: bool
    api_access_module_enabled: bool
    jwt_expiry_minutes: int
    password_min_length: int
    password_require_uppercase: bool
    password_require_number: bool
    password_require_symbol: bool
    created_at: datetime
    updated_at: datetime


class PlatformSettingsUpdate(BaseModel):
    """All optional (PATCH). Only provided fields are changed."""
    model_config = ConfigDict(extra="forbid")
    platform_name: str | None = Field(default=None, min_length=1, max_length=200)
    platform_logo_url: str | None = Field(default=None, max_length=2000)
    support_email: EmailStr | None = None
    support_phone: str | None = Field(default=None, max_length=30)
    default_plan_id: uuid.UUID | None = None
    default_user_limit: int | None = Field(default=None, ge=0)
    default_api_key_limit: int | None = Field(default=None, ge=0)
    default_api_rate_limit: int | None = Field(default=None, ge=0)
    sms_module_enabled: bool | None = None
    voice_module_enabled: bool | None = None
    missed_call_module_enabled: bool | None = None
    api_access_module_enabled: bool | None = None
    jwt_expiry_minutes: int | None = Field(default=None, ge=1, le=1440)
    password_min_length: int | None = Field(default=None, ge=6, le=128)
    password_require_uppercase: bool | None = None
    password_require_number: bool | None = None
    password_require_symbol: bool | None = None
