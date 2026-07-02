"""Repositories for the SMS Campaign Engine.

Tenant-scoped via BaseRepository (filtered by ctx.company_id). Covers campaigns,
their frozen recipient sets, and the per-recipient message rows that make up
campaign history.
"""
from typing import Optional, Sequence

from sqlalchemy import func, or_, select

from app.models.sms import SmsCampaign, SmsCampaignRecipient, SmsMessage
from app.repositories.base import BaseRepository


class SmsCampaignRepository(BaseRepository[SmsCampaign]):
    model = SmsCampaign
    tenant_scoped = True

    async def search(
        self, *, search: str | None = None, status: str | None = None,
        offset: int = 0, limit: int = 20,
    ) -> tuple[Sequence[SmsCampaign], int]:
        stmt = self._base_select()
        if search:
            stmt = stmt.where(SmsCampaign.name.ilike(f"%{search}%"))
        if status is not None:
            stmt = stmt.where(SmsCampaign.status == status)
        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = stmt.order_by(SmsCampaign.created_at.desc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total


class SmsCampaignRecipientRepository(BaseRepository[SmsCampaignRecipient]):
    # Recipients are reached only through a tenant-scoped campaign, so the table
    # itself has no company_id; scope is enforced at the campaign boundary.
    model = SmsCampaignRecipient
    tenant_scoped = False

    async def bulk_add(self, rows: list[dict]) -> None:
        if rows:
            self.session.add_all([SmsCampaignRecipient(**r) for r in rows])
            await self.session.flush()

    async def list_for_campaign(
        self, campaign_id, *, offset: int = 0, limit: int = 50,
    ) -> tuple[Sequence[SmsCampaignRecipient], int]:
        base = select(SmsCampaignRecipient).where(
            SmsCampaignRecipient.campaign_id == campaign_id
        )
        total = (await self.session.execute(
            select(func.count()).select_from(base.subquery())
        )).scalar_one()
        rows = (await self.session.execute(
            base.order_by(SmsCampaignRecipient.created_at.asc()).offset(offset).limit(limit)
        )).scalars().all()
        return rows, total

    async def all_for_campaign(self, campaign_id) -> Sequence[SmsCampaignRecipient]:
        return (await self.session.execute(
            select(SmsCampaignRecipient).where(
                SmsCampaignRecipient.campaign_id == campaign_id
            )
        )).scalars().all()

    async def delete_for_campaign(self, campaign_id) -> None:
        for r in await self.all_for_campaign(campaign_id):
            await self.session.delete(r)
        await self.session.flush()


class SmsMessageRepository(BaseRepository[SmsMessage]):
    model = SmsMessage
    tenant_scoped = True

    async def bulk_add(self, rows: list[dict]) -> list[SmsMessage]:
        objs = [SmsMessage(**r) for r in rows]
        self.session.add_all(objs)
        await self.session.flush()
        return objs

    async def list_for_campaign(
        self, campaign_id, *, status: str | None = None,
        offset: int = 0, limit: int = 50,
    ) -> tuple[Sequence[SmsMessage], int]:
        stmt = self._base_select().where(SmsMessage.campaign_id == campaign_id)
        if status is not None:
            stmt = stmt.where(SmsMessage.status == status)
        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = stmt.order_by(SmsMessage.created_at.asc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    # ----- Analytics / tracking (added for the Tracking & Analytics module) ---
    async def search_messages(
        self, *, campaign_id=None, sender_id: str | None = None, status: str | None = None,
        since=None, until=None, offset: int = 0, limit: int = 50,
    ):
        """Cross-campaign message tracking list, tenant-scoped, with filters."""
        stmt = self._base_select()
        if campaign_id is not None:
            stmt = stmt.where(SmsMessage.campaign_id == campaign_id)
        if sender_id:
            stmt = stmt.where(SmsMessage.sender_id == sender_id)
        if status is not None:
            stmt = stmt.where(SmsMessage.status == status)
        if since is not None:
            stmt = stmt.where(SmsMessage.created_at >= since)
        if until is not None:
            stmt = stmt.where(SmsMessage.created_at <= until)
        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = stmt.order_by(SmsMessage.created_at.desc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    async def status_counts(
        self, *, campaign_id=None, sender_id: str | None = None, since=None, until=None,
    ) -> dict[str, int]:
        """Count messages grouped by status, tenant-scoped, with filters."""
        stmt = (
            self._base_select()
            .with_only_columns(SmsMessage.status, func.count())
            .group_by(SmsMessage.status)
        )
        if campaign_id is not None:
            stmt = stmt.where(SmsMessage.campaign_id == campaign_id)
        if sender_id:
            stmt = stmt.where(SmsMessage.sender_id == sender_id)
        if since is not None:
            stmt = stmt.where(SmsMessage.created_at >= since)
        if until is not None:
            stmt = stmt.where(SmsMessage.created_at <= until)
        rows = (await self.session.execute(stmt)).all()
        return {str(s): int(n) for s, n in rows}

    async def daily_counts(
        self, *, campaign_id=None, sender_id: str | None = None, since=None, until=None,
    ):
        """Per-day (UTC) totals + delivered + failed for time-series charts."""
        day = func.date_trunc("day", SmsMessage.created_at)
        stmt = (
            self._base_select()
            .with_only_columns(
                day.label("day"),
                func.count().label("total"),
                func.count().filter(SmsMessage.status == "delivered").label("delivered"),
                func.count().filter(SmsMessage.status == "failed").label("failed"),
            )
            .group_by(day)
            .order_by(day)
        )
        if campaign_id is not None:
            stmt = stmt.where(SmsMessage.campaign_id == campaign_id)
        if sender_id:
            stmt = stmt.where(SmsMessage.sender_id == sender_id)
        if since is not None:
            stmt = stmt.where(SmsMessage.created_at >= since)
        if until is not None:
            stmt = stmt.where(SmsMessage.created_at <= until)
        return (await self.session.execute(stmt)).all()

    async def get_by_provider_message_id(self, provider_message_id: str):
        """Look up a message by the provider's id — the delivery-callback seam.
        Tenant-scoped: callbacks are resolved within the authenticated company."""
        stmt = self._base_select().where(
            SmsMessage.provider_message_id == provider_message_id
        )
        return (await self.session.execute(stmt.limit(1))).scalars().first()

    async def sent_today_count(self, day_start) -> int:
        """Messages with sent_at today (UTC), tenant-scoped."""
        stmt = (
            self._base_select()
            .with_only_columns(func.count())
            .where(SmsMessage.sent_at >= day_start)
        )
        return (await self.session.execute(stmt)).scalar_one()
