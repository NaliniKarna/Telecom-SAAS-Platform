"""SMS Tracking & Analytics endpoints (Company Admin). Tenant-scoped.

RBAC:
  - analytics widgets / time-series -> sms.analytics
  - message tracking list -> sms.read or sms.manage or sms.analytics
  - delivery-status update / provider callback -> sms.send (operational write)

Voice / Missed-Call / FreePBX are out of scope.
"""
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.deps import (
    CurrentUser,
    get_sms_analytics_service,
    require_permission,
)
from app.core.constants import Permission, SmsMessageStatus
from app.schemas.sms import (
    AnalyticsOverview,
    AnalyticsTimePoint,
    CampaignMessageRead,
    DeliveryCallback,
    DeliveryStatusUpdate,
)
from app.services.sms_analytics_service import SmsAnalyticsService

router = APIRouter(prefix="/sms", tags=["SMS Analytics"])

AnalyticsSvc = Annotated[SmsAnalyticsService, Depends(get_sms_analytics_service)]
CanAnalytics = Annotated[object, Depends(require_permission(Permission.SMS_ANALYTICS.value))]
CanRead = Annotated[object, Depends(require_permission(
    Permission.SMS_READ.value, Permission.SMS_MANAGE.value, Permission.SMS_ANALYTICS.value))]
CanSend = Annotated[object, Depends(require_permission(Permission.SMS_SEND.value))]


def _page(rows, total, page, size, schema):
    return {
        "data": [schema.model_validate(r).model_dump(mode="json") for r in rows],
        "meta": {"page": page, "size": size, "total": total,
                 "pages": (total + size - 1) // size if size else 0},
    }


@router.get("/analytics", response_model=AnalyticsOverview)
async def analytics_overview(
    service: AnalyticsSvc, _: CanAnalytics,
    campaign_id: uuid.UUID | None = None,
    sender_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
):
    data = await service.overview(campaign_id=campaign_id, sender_id=sender_id, since=since, until=until)
    return AnalyticsOverview(**data)


@router.get("/analytics/timeseries", response_model=list[AnalyticsTimePoint])
async def analytics_timeseries(
    service: AnalyticsSvc, _: CanAnalytics,
    campaign_id: uuid.UUID | None = None,
    sender_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
):
    rows = await service.timeseries(campaign_id=campaign_id, sender_id=sender_id, since=since, until=until)
    return [AnalyticsTimePoint(**r) for r in rows]


@router.get("/messages", response_model=dict)
async def list_messages(
    service: AnalyticsSvc, _: CanRead,
    campaign_id: uuid.UUID | None = None,
    sender_id: str | None = None,
    message_status: SmsMessageStatus | None = Query(default=None, alias="status"),
    since: datetime | None = None,
    until: datetime | None = None,
    page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200),
):
    rows, total = await service.list_messages(
        campaign_id=campaign_id, sender_id=sender_id,
        status=message_status.value if message_status else None,
        since=since, until=until, offset=(page - 1) * size, limit=size,
    )
    return _page(rows, total, page, size, CampaignMessageRead)


# --- Delivery lifecycle (extensibility seams; no real gateway wired) --------
@router.patch("/messages/{provider_message_id}/status", response_model=CampaignMessageRead)
async def update_message_status(
    provider_message_id: str, payload: DeliveryStatusUpdate,
    service: AnalyticsSvc, current_user: CurrentUser, _: CanSend,
):
    msg = await service.update_delivery_status(
        provider_message_id, payload.status, error_details=payload.error_details,
    )
    return CampaignMessageRead.model_validate(msg)


@router.post("/delivery-callback", status_code=status.HTTP_202_ACCEPTED)
async def delivery_callback(
    payload: DeliveryCallback, service: AnalyticsSvc, _: CanSend,
):
    """Provider delivery-receipt ingestion point. A real gateway POSTs its DLR
    here; the active provider adapter parses it and the message status is
    updated. Returns 202 whether or not the payload matched a known message, so
    providers don't retry on unrecognized receipts."""
    msg = await service.ingest_callback(payload.model_dump())
    return {"accepted": True, "updated": msg is not None}
