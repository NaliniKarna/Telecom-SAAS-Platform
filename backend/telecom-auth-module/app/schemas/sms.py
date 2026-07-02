"""Pydantic schemas for the SMS Foundation (sender IDs + templates).

Per the architectural dependency rule, schemas import only from pydantic and
app.core.constants — never from deps/services. Campaign/message/analytics
schemas are intentionally excluded from the Foundation.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import (
    SenderApprovalStatus,
    SenderStatus,
    SmsMessageStatus,
    SmsTemplateStatus,
)


# --------------------------------------------------------------------------- #
# Sender IDs
# --------------------------------------------------------------------------- #
class SenderIdCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    sender_id: str = Field(min_length=1, max_length=20)
    description: str | None = Field(default=None, max_length=1000)


class SenderIdUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class SenderIdRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    sender_id: str
    description: str | None
    status: SenderStatus
    approval_status: SenderApprovalStatus
    is_default: bool
    rejection_reason: str | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SenderIdReviewItem(BaseModel):
    """Super-admin queue row: a pending sender plus its company name."""
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    company_id: uuid.UUID
    company_name: str | None = None
    name: str
    sender_id: str
    description: str | None
    approval_status: SenderApprovalStatus
    created_at: datetime


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=500)


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #
class TemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1, max_length=4000)
    status: SmsTemplateStatus | None = None


class TemplateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=255)
    body: str | None = Field(default=None, max_length=4000)
    status: SmsTemplateStatus | None = None


class TemplateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    body: str
    variables: list[str]
    status: SmsTemplateStatus
    created_at: datetime
    updated_at: datetime


class TemplatePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=4000)
    values: dict[str, str] = {}


class TemplatePreviewResponse(BaseModel):
    variables: list[str]
    body: str


# --------------------------------------------------------------------------- #
# Campaigns (SMS Campaign Engine)
# --------------------------------------------------------------------------- #
from app.core.constants import SmsCampaignSource, SmsCampaignStatus  # noqa: E402


class CampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    sender_id: uuid.UUID
    template_id: uuid.UUID
    source_type: SmsCampaignSource
    source_list_id: uuid.UUID | None = None
    contact_ids: list[uuid.UUID] = Field(default_factory=list)


class CampaignUpdate(BaseModel):
    """Draft-only edits."""
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, max_length=255)
    sender_id: uuid.UUID | None = None
    template_id: uuid.UUID | None = None
    source_type: SmsCampaignSource | None = None
    source_list_id: uuid.UUID | None = None
    contact_ids: list[uuid.UUID] | None = None


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schedule_time: datetime


class CampaignRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    sender_id: uuid.UUID | None
    template_id: uuid.UUID | None
    status: SmsCampaignStatus
    source_type: SmsCampaignSource
    schedule_time: datetime | None
    total_recipients: int
    sent_count: int
    delivered_count: int
    failed_count: int
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class CampaignListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    status: SmsCampaignStatus
    source_type: SmsCampaignSource
    schedule_time: datetime | None
    total_recipients: int
    sent_count: int
    delivered_count: int
    failed_count: int
    created_at: datetime


class RecipientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    contact_id: uuid.UUID | None
    phone_e164: str
    resolved_name: str | None
    created_at: datetime


class CampaignMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    campaign_id: uuid.UUID | None
    recipient_phone: str
    sender_id: str | None
    content: str
    status: SmsMessageStatus
    error_details: str | None
    provider_message_id: str | None
    sent_at: datetime | None
    delivered_at: datetime | None
    created_at: datetime


# --------------------------------------------------------------------------- #
# Analytics & tracking (SMS Tracking and Analytics)
# --------------------------------------------------------------------------- #
class AnalyticsOverview(BaseModel):
    total_messages: int
    delivered_messages: int
    failed_messages: int
    sent_messages: int
    queued_messages: int
    delivery_rate: float
    campaign_count: int
    active_campaigns: int


class AnalyticsTimePoint(BaseModel):
    date: str
    total: int
    delivered: int
    failed: int


class DeliveryCallback(BaseModel):
    """Provider delivery-callback payload (dev/test shape). A real adapter
    parses its native format into this normalized form."""
    model_config = ConfigDict(extra="allow")
    provider_message_id: str | None = None
    message_id: str | None = None
    status: str | None = None
    error: str | None = None


class DeliveryStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str = Field(pattern="^(queued|sent|delivered|failed)$")
    error_details: str | None = Field(default=None, max_length=1000)
