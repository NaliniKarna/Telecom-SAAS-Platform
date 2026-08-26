"""API key request/response schemas."""
import ipaddress
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _validate_ip_whitelist(v: list[str] | None) -> list[str] | None:
    """Each entry must be a valid IPv4/IPv6 address or CIDR range.
    None/empty means "allow any IP" — entries are normalized (stripped)."""
    if not v:
        return None
    normalized: list[str] = []
    for entry in v:
        candidate = entry.strip()
        if not candidate:
            continue
        try:
            # strict=False allows host bits set in a CIDR (e.g. 10.0.0.5/24)
            ipaddress.ip_network(candidate, strict=False)
        except ValueError as exc:
            raise ValueError(
                f"'{entry}' is not a valid IP address or CIDR range"
            ) from exc
        normalized.append(candidate)
    return normalized or None


class ApiKeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    # None = never expires. The frontend offers presets (30/60/90/365 days) and
    # a custom date; either way it sends a concrete timestamp or null.
    expires_at: datetime | None = None
    # None/empty = allow requests from any IP. Otherwise a list of IPv4/IPv6
    # addresses or CIDR ranges (e.g. "203.0.113.5", "10.0.0.0/24").
    ip_whitelist: list[str] | None = Field(default=None, max_length=50)

    @field_validator("ip_whitelist")
    @classmethod
    def _check_ip_whitelist(cls, v: list[str] | None) -> list[str] | None:
        return _validate_ip_whitelist(v)


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
    ip_whitelist: list[str] | None = None


class ApiKeyCreated(ApiKeyRead):
    """Returned ONCE on creation — the only time the plaintext key is exposed."""
    api_key: str
