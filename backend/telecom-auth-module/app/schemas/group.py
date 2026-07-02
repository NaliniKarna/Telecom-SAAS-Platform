"""Group request/response schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.constants import GroupStatus, GroupType


class GroupCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    status: GroupStatus = GroupStatus.ACTIVE
    group_type: GroupType = GroupType.INTERNAL


class GroupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    status: GroupStatus | None = None
    # group_type is intentionally immutable after creation.


class GroupListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    status: GroupStatus
    group_type: GroupType
    member_count: int = 0
    created_at: datetime


class GroupRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    status: GroupStatus
    group_type: GroupType
    member_count: int = 0
    created_at: datetime
    updated_at: datetime


class GroupMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID          # membership id
    user_id: uuid.UUID
    email: str
    full_name: str | None = None
    status: str
    added_at: datetime


class GroupFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search: str | None = Field(default=None, max_length=255)
    status: GroupStatus | None = None
    group_type: GroupType | None = None


class AddMembersRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_ids: list[uuid.UUID] = Field(min_length=1)

    @field_validator("user_ids")
    @classmethod
    def _dedupe(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        return list(dict.fromkeys(v))
