"""SMS analytics + delivery-tracking service.

Tenant-scoped aggregations over sms_messages / sms_campaigns:
  - overview widgets (totals, delivery rate, campaign counts),
  - time-series (per-day delivered/failed/total) for charts,
  - cross-campaign message tracking list,
  - delivery-status updates (the lifecycle + provider-callback seam).

All reads are confined to the caller's company via the repositories' context.
Analytics endpoints are gated by sms.analytics; the callback ingestion path is
the extensibility point for a future real gateway (no real provider wired yet).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import SmsCampaignStatus, SmsMessageStatus
from app.core.exceptions import NotFoundError
from app.models.sms import SmsCampaign
from app.repositories.sms_campaign_repository import (
    SmsCampaignRepository,
    SmsMessageRepository,
)
from app.services.audit_service import AuditService
from app.services.sms_provider import DeliveryReceipt, get_sms_provider

logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = (SmsCampaignStatus.SCHEDULED.value, SmsCampaignStatus.PROCESSING.value)


class SmsAnalyticsService:
    def __init__(self, session: AsyncSession, ctx=None, audit: AuditService | None = None):
        self.session = session
        self.ctx = ctx
        self.audit = audit or AuditService(session)
        self.messages = SmsMessageRepository(session, ctx)
        self.campaigns = SmsCampaignRepository(session, ctx)
        self.provider = get_sms_provider()

    @property
    def _company_id(self):
        return self.ctx.company_id if self.ctx else None

    # ===================================================================== #
    # Widgets
    # ===================================================================== #
    async def overview(self, *, campaign_id=None, sender_id=None, since=None, until=None) -> dict:
        counts = await self.messages.status_counts(
            campaign_id=campaign_id, sender_id=sender_id, since=since, until=until,
        )
        total = sum(counts.values())
        delivered = counts.get(SmsMessageStatus.DELIVERED.value, 0)
        failed = counts.get(SmsMessageStatus.FAILED.value, 0)
        sent = counts.get(SmsMessageStatus.SENT.value, 0)
        queued = counts.get(SmsMessageStatus.QUEUED.value, 0)
        # Delivery rate = delivered / (messages that left the queue).
        attempted = delivered + failed + sent
        delivery_rate = round(delivered / attempted * 100, 2) if attempted else 0.0

        campaign_count = await self.session.scalar(
            select(func.count(SmsCampaign.id)).where(
                SmsCampaign.company_id == self._company_id,
                SmsCampaign.deleted_at.is_(None),
            )
        )
        active_campaigns = await self.session.scalar(
            select(func.count(SmsCampaign.id)).where(
                SmsCampaign.company_id == self._company_id,
                SmsCampaign.deleted_at.is_(None),
                SmsCampaign.status.in_(_ACTIVE_STATUSES),
            )
        )
        return {
            "total_messages": total,
            "delivered_messages": delivered,
            "failed_messages": failed,
            "sent_messages": sent,
            "queued_messages": queued,
            "delivery_rate": delivery_rate,
            "campaign_count": int(campaign_count or 0),
            "active_campaigns": int(active_campaigns or 0),
        }

    async def timeseries(self, *, campaign_id=None, sender_id=None, since=None, until=None) -> list[dict]:
        rows = await self.messages.daily_counts(
            campaign_id=campaign_id, sender_id=sender_id, since=since, until=until,
        )
        out = []
        for r in rows:
            day = r.day
            out.append({
                "date": day.date().isoformat() if hasattr(day, "date") else str(day),
                "total": int(r.total or 0),
                "delivered": int(r.delivered or 0),
                "failed": int(r.failed or 0),
            })
        return out

    # ===================================================================== #
    # Message tracking
    # ===================================================================== #
    async def list_messages(self, *, campaign_id=None, sender_id=None, status=None,
                            since=None, until=None, offset=0, limit=50):
        return await self.messages.search_messages(
            campaign_id=campaign_id, sender_id=sender_id, status=status,
            since=since, until=until, offset=offset, limit=limit,
        )

    # ===================================================================== #
    # Delivery lifecycle (status updates + provider-callback ingestion)
    # ===================================================================== #
    async def update_delivery_status(
        self, provider_message_id: str, status: str, *, error_details: str | None = None,
    ):
        """Apply a delivery-status transition to the message identified by the
        provider's id. This is the lifecycle hook a real gateway's callback
        drives; it's tenant-scoped so a company only updates its own messages."""
        msg = await self.messages.get_by_provider_message_id(provider_message_id)
        if msg is None:
            raise NotFoundError("Message not found for provider id")
        now = datetime.now(timezone.utc)
        msg.status = status
        if status == SmsMessageStatus.DELIVERED.value:
            msg.delivered_at = msg.delivered_at or now
            if msg.sent_at is None:
                msg.sent_at = now
        elif status == SmsMessageStatus.SENT.value:
            msg.sent_at = msg.sent_at or now
        elif status == SmsMessageStatus.FAILED.value:
            msg.error_details = error_details or msg.error_details
        await self.session.flush()
        # Keep the owning campaign's denormalized counters consistent.
        if msg.campaign_id is not None:
            await self._recount_campaign(msg.campaign_id)
        await self.session.commit()
        await self.session.refresh(msg)
        return msg

    async def ingest_callback(self, payload: dict):
        """Provider-callback ingestion seam. Parses a raw gateway payload via the
        active provider adapter, then applies the resulting status update. No
        real gateway is wired; NullSmsProvider parses a simple normalized shape.
        Returns the updated message, or None if the payload wasn't a recognized
        delivery receipt."""
        receipt: DeliveryReceipt | None = self.provider.parse_callback(payload)
        if receipt is None:
            return None
        return await self.update_delivery_status(
            receipt.provider_message_id, receipt.status, error_details=receipt.error_details,
        )

    async def _recount_campaign(self, campaign_id) -> None:
        counts = await self.messages.status_counts(campaign_id=campaign_id)
        campaign = await self.campaigns.get_by_id(campaign_id)
        if campaign is None:
            return
        delivered = counts.get(SmsMessageStatus.DELIVERED.value, 0)
        failed = counts.get(SmsMessageStatus.FAILED.value, 0)
        sent = counts.get(SmsMessageStatus.SENT.value, 0)
        campaign.delivered_count = delivered
        campaign.failed_count = failed
        # sent_count counts everything that left the queue (sent or delivered).
        campaign.sent_count = sent + delivered
        await self.session.flush()
