"""TTS Usage Metering data access.

Deliberately NOT BaseRepository subclasses: these tables aren't tenant-scoped
in the request-context sense (company_id is always passed explicitly by
TtsUsageService, which is itself company-agnostic and reusable from any
caller — campaigns, previews, a future admin usage report), and the whole
point of this repository is the row-locking (`SELECT ... FOR UPDATE`)
primitives the generic base doesn't provide.

Lock ordering (see app.services.tts_usage_service docstring for the full
rationale): every code path that touches both a TtsUsage row and a
TtsUsageReservation row locks TtsUsage FIRST, then the reservation — this
file's methods are written in that order and callers must not reverse it,
or two concurrent requests can deadlock instead of correctly serializing.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.voice_campaign import TtsUsage, TtsUsageReservation


class TtsUsageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_for_update(self, company_id, usage_month: date) -> TtsUsage:
        """Ensure the month's row exists, then return it LOCKED for the
        duration of the caller's transaction. The upsert-then-lock pattern
        is what makes concurrent reserve() calls for the same company+month
        serialize correctly instead of racing on row creation."""
        stmt = pg_insert(TtsUsage).values(
            company_id=company_id, usage_month=usage_month,
            consumed_characters=0, reserved_characters=0, request_count=0,
        ).on_conflict_do_nothing(
            index_elements=["company_id", "usage_month"],
        )
        await self.session.execute(stmt)

        locked = await self.session.execute(
            select(TtsUsage)
            .where(TtsUsage.company_id == company_id, TtsUsage.usage_month == usage_month)
            .with_for_update()
        )
        return locked.scalar_one()

    async def get_readonly(self, company_id, usage_month: date) -> TtsUsage | None:
        """Unlocked read for display purposes (quota summaries, campaign
        creation UI) — never used inside a reserve/consume/release
        transaction, which must always go through get_for_update()."""
        res = await self.session.execute(
            select(TtsUsage).where(
                TtsUsage.company_id == company_id, TtsUsage.usage_month == usage_month,
            )
        )
        return res.scalar_one_or_none()


class TtsUsageReservationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_reference(
        self, reference_type: str, reference_id, *, for_update: bool = False,
    ) -> TtsUsageReservation | None:
        stmt = select(TtsUsageReservation).where(
            TtsUsageReservation.reference_type == reference_type,
            TtsUsageReservation.reference_id == reference_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create(
        self, *, company_id, usage_month: date, reference_type: str, reference_id,
        reserved_characters: int,
    ) -> TtsUsageReservation:
        reservation = TtsUsageReservation(
            company_id=company_id,
            usage_month=usage_month,
            reference_type=reference_type,
            reference_id=reference_id,
            reserved_characters=reserved_characters,
            consumed_characters=0,
            status="open",
        )
        self.session.add(reservation)
        await self.session.flush()
        return reservation
