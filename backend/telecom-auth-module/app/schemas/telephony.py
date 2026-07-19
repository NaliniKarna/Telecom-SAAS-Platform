"""Telephony connection schemas.

The AMI secret is WRITE-ONLY: accepted on create/update, never serialized back.
Reads expose `secret_set: bool` so the UI can show whether a secret is stored
without ever revealing it. `is_platform_default` is True when company_id is null.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TelephonyConnectionBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=5038, ge=1, le=65535)
    ami_username: str = Field(min_length=1, max_length=255)
    use_tls: bool = False
    enabled: bool = True


class TelephonyConnectionCreate(TelephonyConnectionBase):
    # Required at creation; stored encrypted, never returned.
    ami_secret: str = Field(min_length=1, max_length=512)


class TelephonyConnectionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    host: Optional[str] = Field(default=None, min_length=1, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    ami_username: Optional[str] = Field(default=None, min_length=1, max_length=255)
    # Optional on update — omit to keep the existing secret.
    ami_secret: Optional[str] = Field(default=None, min_length=1, max_length=512)
    use_tls: Optional[bool] = None
    enabled: Optional[bool] = None


class TelephonyConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: Optional[uuid.UUID]
    name: str
    description: Optional[str]
    host: str
    port: int
    ami_username: str
    use_tls: bool
    enabled: bool
    last_status: str
    last_checked_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime
    updated_at: datetime

    # Derived, never the secret itself.
    is_platform_default: bool = False
    secret_set: bool = True

    @classmethod
    def from_model(cls, m) -> "TelephonyConnectionRead":
        return cls(
            id=m.id, company_id=m.company_id, name=m.name, description=m.description,
            host=m.host, port=m.port, ami_username=m.ami_username, use_tls=m.use_tls,
            enabled=m.enabled, last_status=m.last_status,
            last_checked_at=m.last_checked_at, last_error=m.last_error,
            created_at=m.created_at, updated_at=m.updated_at,
            is_platform_default=(m.company_id is None),
            secret_set=bool(m.ami_secret_encrypted),
        )


class ConnectionTestResult(BaseModel):
    connected: bool
    detail: str
    latency_ms: Optional[int] = None
    provider: str
    checked_at: datetime


class EffectiveStatus(BaseModel):
    """The connection that would actually be used for the caller's company,
    after hybrid resolution (own override else platform default)."""
    source: str  # "company" | "platform-default" | "none"
    connection: Optional[TelephonyConnectionRead] = None
    status: Optional[ConnectionTestResult] = None
