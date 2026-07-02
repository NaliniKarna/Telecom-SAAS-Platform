"""SMS Campaign Engine endpoints (Company Admin). Tenant-scoped.

RBAC:
  - reads/create/edit-draft -> sms.manage (campaign authoring is a management op)
  - schedule / send / cancel -> sms.send
Listing/history reads accept sms.read OR sms.manage.

Analytics endpoints are intentionally NOT part of this module.
"""
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.deps import (
    CurrentUser,
    get_sms_campaign_service,
    require_permission,
)
from app.core.constants import Permission, SmsCampaignStatus, SmsMessageStatus
from app.schemas.sms import (
    CampaignCreate,
    CampaignListItem,
    CampaignMessageRead,
    CampaignRead,
    CampaignUpdate,
    RecipientRead,
    ScheduleRequest,
)
from app.services.sms_campaign_service import SmsCampaignService

router = APIRouter(prefix="/sms/campaigns", tags=["SMS Campaigns"])

CampaignSvc = Annotated[SmsCampaignService, Depends(get_sms_campaign_service)]
CanRead = Annotated[object, Depends(require_permission(Permission.SMS_READ.value, Permission.SMS_MANAGE.value))]
CanManage = Annotated[object, Depends(require_permission(Permission.SMS_MANAGE.value))]
CanSend = Annotated[object, Depends(require_permission(Permission.SMS_SEND.value))]


def _ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _page(rows, total, page, size, schema):
    return {
        "data": [schema.model_validate(r).model_dump(mode="json") for r in rows],
        "meta": {"page": page, "size": size, "total": total,
                 "pages": (total + size - 1) // size if size else 0},
    }


@router.get("", response_model=dict)
async def list_campaigns(
    service: CampaignSvc, _: CanRead,
    search: str | None = None,
    campaign_status: SmsCampaignStatus | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
):
    rows, total = await service.list_campaigns(
        search=search,
        status=campaign_status.value if campaign_status else None,
        offset=(page - 1) * size, limit=size,
    )
    return _page(rows, total, page, size, CampaignListItem)


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(payload: CampaignCreate, service: CampaignSvc,
                          current_user: CurrentUser, request: Request, _: CanManage):
    c = await service.create_campaign(payload, actor_id=current_user.id, ip=_ip(request))
    return CampaignRead.model_validate(c)


@router.get("/{campaign_id}", response_model=CampaignRead)
async def get_campaign(campaign_id: uuid.UUID, service: CampaignSvc, _: CanRead):
    return CampaignRead.model_validate(await service.get_campaign(campaign_id))


@router.patch("/{campaign_id}", response_model=CampaignRead)
async def update_campaign(campaign_id: uuid.UUID, payload: CampaignUpdate, service: CampaignSvc,
                          current_user: CurrentUser, request: Request, _: CanManage):
    c = await service.update_campaign(campaign_id, payload, actor_id=current_user.id, ip=_ip(request))
    return CampaignRead.model_validate(c)


@router.post("/{campaign_id}/schedule", response_model=CampaignRead)
async def schedule_campaign(campaign_id: uuid.UUID, payload: ScheduleRequest, service: CampaignSvc,
                            current_user: CurrentUser, request: Request, _: CanSend):
    c = await service.schedule_campaign(campaign_id, payload.schedule_time,
                                        actor_id=current_user.id, ip=_ip(request))
    return CampaignRead.model_validate(c)


@router.post("/{campaign_id}/send", response_model=CampaignRead)
async def send_campaign(campaign_id: uuid.UUID, service: CampaignSvc,
                        current_user: CurrentUser, request: Request, _: CanSend):
    c = await service.send_campaign(campaign_id, actor_id=current_user.id, ip=_ip(request))
    return CampaignRead.model_validate(c)


@router.post("/{campaign_id}/cancel", response_model=CampaignRead)
async def cancel_campaign(campaign_id: uuid.UUID, service: CampaignSvc,
                          current_user: CurrentUser, request: Request, _: CanSend):
    c = await service.cancel_campaign(campaign_id, actor_id=current_user.id, ip=_ip(request))
    return CampaignRead.model_validate(c)


@router.get("/{campaign_id}/recipients", response_model=dict)
async def list_recipients(campaign_id: uuid.UUID, service: CampaignSvc, _: CanRead,
                          page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200)):
    rows, total = await service.list_recipients(campaign_id, offset=(page - 1) * size, limit=size)
    return _page(rows, total, page, size, RecipientRead)


@router.get("/{campaign_id}/messages", response_model=dict)
async def list_messages(campaign_id: uuid.UUID, service: CampaignSvc, _: CanRead,
                        message_status: SmsMessageStatus | None = Query(default=None, alias="status"),
                        page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200)):
    rows, total = await service.list_messages(
        campaign_id, status=message_status.value if message_status else None,
        offset=(page - 1) * size, limit=size,
    )
    return _page(rows, total, page, size, CampaignMessageRead)
