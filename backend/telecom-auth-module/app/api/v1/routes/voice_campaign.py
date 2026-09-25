"""Voice Campaign Foundation endpoints (Company Admin). Tenant-scoped.

RBAC:
  - reads (list/detail/recipients/estimate/usage) -> ai_voice.campaign.read
  - create/edit-draft/delete/start/cancel          -> ai_voice.campaign.manage

Strict Phase 4A scope boundary (see app.services.voice_campaign_service):
no endpoint here originates a call, generates campaign audio, or publishes
a Kafka event. POST /{campaign_id}/start is the one write endpoint that
does meaningful work — it commits the immutable recipient snapshot and
atomically reserves TTS quota, then stops. Everything past that (Kafka ->
TTS -> PBX) is Phase 4B.

Route ordering note: "/usage/summary" is registered BEFORE "/{campaign_id}"
so it isn't swallowed by the dynamic path (the same lesson as the
GET /companies/plans fix — see IMPLEMENTATION-REPORT.md history).
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.deps import (
    CurrentUser,
    get_voice_campaign_service,
    require_permission,
)
from app.core.constants import Permission, VoiceCampaignRecipientStatus, VoiceCampaignStatus
from app.core.http import client_ip
from app.schemas.voice_campaign import (
    TtsUsageSummary,
    VoiceCampaignCreate,
    VoiceCampaignEstimate,
    VoiceCampaignListItem,
    VoiceCampaignRead,
    VoiceCampaignRecipientRead,
    VoiceCampaignUpdate,
)
from app.services.voice_campaign_service import VoiceCampaignService

router = APIRouter(prefix="/voice-campaigns", tags=["Voice Campaigns"])

CampaignSvc = Annotated[VoiceCampaignService, Depends(get_voice_campaign_service)]
CanRead = Annotated[object, Depends(require_permission(Permission.AI_VOICE_CAMPAIGN_READ.value))]
CanManage = Annotated[object, Depends(require_permission(Permission.AI_VOICE_CAMPAIGN_MANAGE.value))]


def _page(rows, total, page, size, schema):
    return {
        "data": [schema.model_validate(r).model_dump(mode="json") for r in rows],
        "meta": {"page": page, "size": size, "total": total,
                 "pages": (total + size - 1) // size if size else 0},
    }


# =========================================================================== #
# TTS usage summary (registered before "/{campaign_id}" — see module docstring)
# =========================================================================== #
@router.get("/usage/summary", response_model=TtsUsageSummary)
async def usage_summary(service: CampaignSvc, _: CanRead):
    summary = await service.get_usage_summary()
    return TtsUsageSummary(
        usage_month=summary.usage_month, monthly_limit=summary.monthly_limit,
        consumed_characters=summary.consumed_characters,
        reserved_characters=summary.reserved_characters,
        available_characters=summary.available_characters,
    )


# =========================================================================== #
# Campaign CRUD (draft-only edits enforced in the service layer)
# =========================================================================== #
@router.get("", response_model=dict)
async def list_campaigns(
    service: CampaignSvc, _: CanRead,
    search: str | None = None,
    campaign_status: VoiceCampaignStatus | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
):
    rows, total = await service.list_campaigns(
        search=search,
        status=campaign_status.value if campaign_status else None,
        offset=(page - 1) * size, limit=size,
    )
    return _page(rows, total, page, size, VoiceCampaignListItem)


@router.post("", response_model=VoiceCampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: VoiceCampaignCreate, service: CampaignSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
):
    c = await service.create_campaign(payload, actor_id=current_user.id, ip=client_ip(request))
    return VoiceCampaignRead.model_validate(c)


@router.get("/{campaign_id}", response_model=VoiceCampaignRead)
async def get_campaign(campaign_id: uuid.UUID, service: CampaignSvc, _: CanRead):
    return VoiceCampaignRead.model_validate(await service.get_campaign(campaign_id))


@router.patch("/{campaign_id}", response_model=VoiceCampaignRead)
async def update_campaign(
    campaign_id: uuid.UUID, payload: VoiceCampaignUpdate, service: CampaignSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
):
    c = await service.update_campaign(
        campaign_id, payload, actor_id=current_user.id, ip=client_ip(request),
    )
    return VoiceCampaignRead.model_validate(c)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(
    campaign_id: uuid.UUID, service: CampaignSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
):
    await service.delete_campaign(campaign_id, actor_id=current_user.id, ip=client_ip(request))


# =========================================================================== #
# Pre-start estimate (read-only, safe to poll while editing a draft)
# =========================================================================== #
@router.get("/{campaign_id}/estimate", response_model=VoiceCampaignEstimate)
async def estimate_campaign(campaign_id: uuid.UUID, service: CampaignSvc, _: CanRead):
    recipient_count, estimated_characters, usage_summary, errors, can_start = (
        await service.estimate(campaign_id)
    )
    return VoiceCampaignEstimate(
        recipient_count=recipient_count,
        estimated_characters=estimated_characters,
        usage=TtsUsageSummary(
            usage_month=usage_summary.usage_month,
            monthly_limit=usage_summary.monthly_limit,
            consumed_characters=usage_summary.consumed_characters,
            reserved_characters=usage_summary.reserved_characters,
            available_characters=usage_summary.available_characters,
        ),
        can_start=can_start,
        errors=errors,
    )


# =========================================================================== #
# Start boundary + cancel
# =========================================================================== #
@router.post("/{campaign_id}/start", response_model=VoiceCampaignRead)
async def start_campaign(
    campaign_id: uuid.UUID, service: CampaignSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
):
    c = await service.start_campaign(campaign_id, actor_id=current_user.id, ip=client_ip(request))
    return VoiceCampaignRead.model_validate(c)


@router.post("/{campaign_id}/cancel", response_model=VoiceCampaignRead)
async def cancel_campaign(
    campaign_id: uuid.UUID, service: CampaignSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
):
    c = await service.cancel_campaign(campaign_id, actor_id=current_user.id, ip=client_ip(request))
    return VoiceCampaignRead.model_validate(c)


@router.post(
    "/{campaign_id}/recipients/{recipient_id}/retry", response_model=VoiceCampaignRecipientRead,
)
async def retry_recipient(
    campaign_id: uuid.UUID, recipient_id: uuid.UUID, service: CampaignSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
):
    """Manual retry (Phase 4B) — only a FAILED/NO_ANSWER/BUSY recipient is
    retryable; a COMPLETED one is rejected by the service layer so a retry
    can never place a second call for a recipient who already succeeded."""
    r = await service.retry_recipient(
        campaign_id, recipient_id, actor_id=current_user.id, ip=client_ip(request),
    )
    return VoiceCampaignRecipientRead.model_validate(r)


# =========================================================================== #
# Recipients (frozen snapshot — read-only, populated only after Start)
# =========================================================================== #
@router.get("/{campaign_id}/recipients", response_model=dict)
async def list_recipients(
    campaign_id: uuid.UUID, service: CampaignSvc, _: CanRead,
    recipient_status: VoiceCampaignRecipientStatus | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200),
):
    rows, total = await service.list_recipients(
        campaign_id, status=recipient_status.value if recipient_status else None,
        offset=(page - 1) * size, limit=size,
    )
    return _page(rows, total, page, size, VoiceCampaignRecipientRead)
