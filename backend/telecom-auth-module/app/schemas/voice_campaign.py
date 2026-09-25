"""Pydantic schemas for the Voice Campaign Foundation + TTS Usage Metering
(Phase 4A). No call/PBX/execution fields here — those belong to Phase 4B.
"""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import VoiceCampaignRecipientStatus, VoiceCampaignStatus


# --------------------------------------------------------------------------- #
# TTS usage
# --------------------------------------------------------------------------- #
class TtsUsageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    usage_month: date
    monthly_limit: int | None
    consumed_characters: int
    reserved_characters: int
    available_characters: int | None  # None = unlimited


# --------------------------------------------------------------------------- #
# Campaign create / update (draft-only)
# --------------------------------------------------------------------------- #
class VoiceCampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    contact_list_id: uuid.UUID
    voice_template_id: uuid.UUID
    # Optional override; defaults to the template's own voice at Start time.
    voice_id: uuid.UUID | None = None
    scheduled_at: datetime | None = None


class VoiceCampaignUpdate(BaseModel):
    """Draft-only edits — enforced by VoiceCampaignService.update_campaign()."""
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=255)
    contact_list_id: uuid.UUID | None = None
    voice_template_id: uuid.UUID | None = None
    voice_id: uuid.UUID | None = None
    scheduled_at: datetime | None = None


# --------------------------------------------------------------------------- #
# Campaign reads
# --------------------------------------------------------------------------- #
class VoiceCampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    contact_list_id: uuid.UUID | None
    voice_template_id: uuid.UUID | None
    voice_id: uuid.UUID | None
    resolved_voice_id: uuid.UUID | None
    status: VoiceCampaignStatus
    total_recipients: int
    estimated_tts_characters: int
    scheduled_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class VoiceCampaignListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    status: VoiceCampaignStatus
    total_recipients: int
    estimated_tts_characters: int
    scheduled_at: datetime | None
    created_at: datetime


class VoiceCampaignRecipientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    contact_id: uuid.UUID | None
    phone_e164: str
    resolved_name: str | None
    rendered_text: str
    tts_char_count: int
    audio_id: uuid.UUID | None
    status: VoiceCampaignRecipientStatus
    error_message: str | None
    correlation_id: str
    created_at: datetime


# --------------------------------------------------------------------------- #
# Pre-start estimate (draft-time, read-only, callable repeatedly)
# --------------------------------------------------------------------------- #
class VoiceCampaignEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient_count: int
    estimated_characters: int
    usage: TtsUsageSummary
    can_start: bool
    errors: list[str] = Field(default_factory=list)
