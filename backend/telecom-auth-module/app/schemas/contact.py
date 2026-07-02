"""Contact & contact-list request/response schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.constants import ContactNumberType, ContactStatus


# --------------------------------------------------------------------------- #
# Contacts
# --------------------------------------------------------------------------- #
class ContactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    # Raw numbers as typed; the service normalizes to E.164.
    mobile: str | None = Field(default=None, max_length=40)
    landline: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)
    status: ContactStatus = ContactStatus.ACTIVE

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, v: list[str]) -> list[str]:
        seen = []
        for t in v or []:
            t = (t or "").strip()
            if t and t not in seen:
                seen.append(t)
        return seen


class ContactUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    mobile: str | None = Field(default=None, max_length=40)
    landline: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    tags: list[str] | None = None
    notes: str | None = Field(default=None, max_length=2000)
    status: ContactStatus | None = None

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, v):
        if v is None:
            return None
        seen = []
        for t in v:
            t = (t or "").strip()
            if t and t not in seen:
                seen.append(t)
        return seen


class ContactRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    first_name: str | None
    last_name: str | None
    mobile_raw: str | None
    mobile_e164: str | None
    landline_raw: str | None
    landline_e164: str | None
    number_type: ContactNumberType
    email: str | None
    tags: list[str]
    notes: str | None
    status: ContactStatus
    created_at: datetime
    updated_at: datetime


class ContactListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    first_name: str | None
    last_name: str | None
    mobile_e164: str | None
    email: str | None
    tags: list[str]
    status: ContactStatus
    created_at: datetime


class ContactFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search: str | None = Field(default=None, max_length=255)
    status: ContactStatus | None = None
    tag: str | None = Field(default=None, max_length=100)


# --------------------------------------------------------------------------- #
# Contact lists
# --------------------------------------------------------------------------- #
class ContactListCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class ContactListUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class ContactListRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    member_count: int = 0
    created_at: datetime
    updated_at: datetime


class ContactListListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    member_count: int = 0
    created_at: datetime


class AddContactsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contact_ids: list[uuid.UUID] = Field(min_length=1)

    @field_validator("contact_ids")
    @classmethod
    def _dedupe(cls, v):
        return list(dict.fromkeys(v))


class ContactListMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID            # membership id
    contact_id: uuid.UUID
    first_name: str | None = None
    last_name: str | None = None
    mobile_e164: str | None = None
    email: str | None = None
    added_at: datetime


# --------------------------------------------------------------------------- #
# CSV import (C3)
# --------------------------------------------------------------------------- #
class ImportRowResult(BaseModel):
    """One parsed CSV row after validation/normalization (preview)."""
    row_number: int
    first_name: str | None = None
    last_name: str | None = None
    mobile: str | None = None
    mobile_e164: str | None = None
    landline: str | None = None
    landline_e164: str | None = None
    email: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    status: str = "active"
    # valid | invalid | duplicate
    row_status: str
    errors: list[str] = Field(default_factory=list)


class ImportPreviewResponse(BaseModel):
    total: int
    valid: int
    invalid: int
    duplicate: int
    rows: list[ImportRowResult]


class ImportCommitRow(BaseModel):
    """A row the client confirms for import. Raw mobile/landline are re-normalized
    server-side (never trust client-computed e164)."""
    model_config = ConfigDict(extra="ignore")
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    mobile: str | None = Field(default=None, max_length=40)
    landline: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = Field(default=None, max_length=2000)
    status: ContactStatus = ContactStatus.ACTIVE


class ImportCommitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: list[ImportCommitRow] = Field(min_length=1, max_length=5000)
    # How to handle rows that collide with an existing contact.
    on_duplicate: str = Field(default="skip", pattern="^(skip|import_anyway)$")


class ImportCommitResponse(BaseModel):
    imported: int
    skipped_duplicates: int
    failed: int
    errors: list[str] = Field(default_factory=list)