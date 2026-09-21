"""Pydantic schemas for the AI Voice / TTS foundation.

Voice library, Voice Templates, template rendering, and TTS preview.
Deliberately excludes Voice Campaigns, recipients, and anything call/PBX
related — those are a later phase per the spec.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import VoiceStatus, VoiceTemplateStatus


# --------------------------------------------------------------------------- #
# Voice library
# --------------------------------------------------------------------------- #
class VoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    language: str
    gender: str | None
    description: str | None
    provider: str
    provider_voice_id: str
    status: VoiceStatus
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Voice Templates
# --------------------------------------------------------------------------- #
class VoiceTemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    text: str = Field(min_length=1, max_length=4000)
    language: str = Field(min_length=2, max_length=20)
    voice_id: uuid.UUID
    status: VoiceTemplateStatus | None = None


class VoiceTemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    text: str | None = Field(default=None, max_length=4000)
    language: str | None = Field(default=None, max_length=20)
    voice_id: uuid.UUID | None = None
    status: VoiceTemplateStatus | None = None


class VoiceTemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: str | None
    text: str
    language: str
    voice_id: uuid.UUID
    variables: list[str]
    status: VoiceTemplateStatus
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Rendering + TTS preview
# --------------------------------------------------------------------------- #
class VoiceTemplateRenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict[str, str] = Field(default_factory=dict)


class VoiceTemplateRenderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rendered_text: str
    missing_variables: list[str]


class TtsPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict[str, str] = Field(default_factory=dict)
    # Optional per-request voice override; defaults to the template's voice.
    voice_id: uuid.UUID | None = None


class TtsPreviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    voice_template_id: uuid.UUID
    voice_id: uuid.UUID
    rendered_text: str
    audio_url: str
    duration_seconds: int | None
    char_count: int
    created_at: datetime
