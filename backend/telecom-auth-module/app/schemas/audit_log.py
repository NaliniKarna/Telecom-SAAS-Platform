"""Audit log DTOs (read/query side only — writes go through AuditService)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuditLogRead(BaseModel):
    """A single audit row, enriched with actor/company display info."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    action: str
    entity_type: str
    entity_id: str | None
    description: str | None
    company_id: uuid.UUID | None
    company_name: str | None = None
    actor_id: uuid.UUID | None
    actor_email: str | None = None
    actor_name: str | None = None
    ip_address: str | None = None
    old_values: dict | None = None
    new_values: dict | None = None
    created_at: datetime

    @field_validator("ip_address", mode="before")
    @classmethod
    def _ip_to_str(cls, v):
        return str(v) if v is not None else None


class AuditLogFilter(BaseModel):
    """Filter params: company, user, action, module (entity_type), date range."""
    model_config = ConfigDict(extra="forbid")
    search: str | None = Field(default=None, max_length=255)
    company_id: uuid.UUID | None = None
    actor_id: uuid.UUID | None = None
    action: str | None = Field(default=None, max_length=100)
    entity_type: str | None = Field(default=None, max_length=100)
    date_from: datetime | None = None
    date_to: datetime | None = None
    sort_dir: str = Field(default="desc", pattern="^(asc|desc)$")

    @field_validator("date_to")
    @classmethod
    def _check_range(cls, v, info):
        df = info.data.get("date_from")
        if v is not None and df is not None and v < df:
            raise ValueError("date_to must be on or after date_from")
        return v


class AuditFacets(BaseModel):
    """Distinct values for populating filter dropdowns."""
    actions: list[str]
    modules: list[str]
