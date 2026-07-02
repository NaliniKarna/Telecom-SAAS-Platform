"""Company change-request DTOs (approval workflow)."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FieldDiff(BaseModel):
    old: str | None = None
    new: str | None = None


class ChangeRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str | None = None
    requested_by: uuid.UUID | None = None
    requester_name: str | None = None
    status: str
    changes: dict[str, FieldDiff]
    decision_reason: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=500)


# Returned by the company-settings PATCH so the UI knows whether the change took
# effect immediately or was queued for approval.
class SettingsUpdateResult(BaseModel):
    immediate_applied: list[str] = []
    pending_request: ChangeRequestRead | None = None
