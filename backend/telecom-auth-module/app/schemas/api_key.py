"""API key request/response schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    # None = never expires. The frontend offers presets (30/60/90/365 days) and
    # a custom date; either way it sends a concrete timestamp or null.
    expires_at: datetime | None = None


class ApiKeyRead(BaseModel):
    """Safe representation — never includes the secret."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    key_prefix: str
    status: str  # active | revoked | expired (derived)
    expires_at: datetime | None
    last_used_at: datetime | None
    usage_count: int
    revoked_at: datetime | None
    created_at: datetime


class ApiKeyCreated(ApiKeyRead):
    """Returned ONCE on creation — the only time the plaintext key is exposed."""
    api_key: str
