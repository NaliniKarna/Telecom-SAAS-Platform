"""Repositories for the Voice Campaign Foundation (Phase 4A).

Tenant scoping mirrors app.repositories.sms_campaign_repository exactly:
VoiceCampaign is tenant-scoped (has company_id); recipients and audio
records are reached only through an already tenant-verified campaign, so
those two repositories disable the base tenant filter and scope manually
by campaign_id/recipient_id instead.
"""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.models.voice_campaign import (
    VoiceCampaign,
    VoiceCampaignAudio,
    VoiceCampaignRecipient,
    VoiceCampaignRecipientAttempt,
)
from app.repositories.base import BaseRepository


class VoiceCampaignRepository(BaseRepository[VoiceCampaign]):
    model = VoiceCampaign
    tenant_scoped = True

    async def search(
        self, *, search: str | None = None, status: str | None = None,
        offset: int = 0, limit: int = 20,
    ) -> tuple[Sequence[VoiceCampaign], int]:
        stmt = self._base_select()
        if search:
            stmt = stmt.where(VoiceCampaign.name.ilike(f"%{search}%"))
        if status is not None:
            stmt = stmt.where(VoiceCampaign.status == status)
        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = stmt.order_by(VoiceCampaign.created_at.desc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    async def get_by_id_for_update(self, campaign_id) -> VoiceCampaign | None:
        """Lock the campaign row for the duration of Start()/cancel()'s
        transaction — this is the primary safeguard against two concurrent
        requests both trying to start (or start + cancel) the same
        campaign: the second blocks until the first commits or rolls back,
        then re-reads the (by-then-updated) status and no-ops correctly."""
        stmt = self._base_select().where(VoiceCampaign.id == campaign_id).with_for_update()
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()


class VoiceCampaignRecipientRepository(BaseRepository[VoiceCampaignRecipient]):
    # Recipients are reached only through a tenant-scoped campaign (see
    # SmsCampaignRecipientRepository for the identical convention).
    model = VoiceCampaignRecipient
    tenant_scoped = False

    async def bulk_add(self, rows: list[dict]) -> list[VoiceCampaignRecipient]:
        objs = [VoiceCampaignRecipient(**r) for r in rows]
        self.session.add_all(objs)
        await self.session.flush()
        return objs

    async def list_for_campaign(
        self, campaign_id, *, status: str | None = None, offset: int = 0, limit: int = 50,
    ) -> tuple[Sequence[VoiceCampaignRecipient], int]:
        stmt = select(VoiceCampaignRecipient).where(
            VoiceCampaignRecipient.campaign_id == campaign_id
        )
        if status is not None:
            stmt = stmt.where(VoiceCampaignRecipient.status == status)
        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = stmt.order_by(VoiceCampaignRecipient.created_at.asc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    async def count_for_campaign(self, campaign_id) -> int:
        return (await self.session.execute(
            select(func.count()).where(VoiceCampaignRecipient.campaign_id == campaign_id)
        )).scalar_one()

    async def count_by_status(self, campaign_id) -> dict[str, int]:
        """Used by VoiceCampaignService.finalize_if_done for the campaign
        aggregate rollup (Phase 4B) — one grouped COUNT, not N status
        checks, so it stays cheap even for large campaigns."""
        rows = (await self.session.execute(
            select(VoiceCampaignRecipient.status, func.count())
            .where(VoiceCampaignRecipient.campaign_id == campaign_id)
            .group_by(VoiceCampaignRecipient.status)
        )).all()
        return {status: int(n) for status, n in rows}

    async def get_by_correlation_id(self, correlation_id: str) -> VoiceCampaignRecipient | None:
        res = await self.session.execute(
            select(VoiceCampaignRecipient).where(
                VoiceCampaignRecipient.correlation_id == correlation_id
            )
        )
        return res.scalar_one_or_none()

    async def try_claim_for_processing(
        self, recipient_id, *, allowed_from: list[str], expected_attempt: int | None = None,
    ) -> VoiceCampaignRecipient | None:
        """Atomically transition recipient_id to 'processing' IF its current
        status is one of allowed_from — a single UPDATE...WHERE...RETURNING,
        so under concurrent workers exactly one caller's UPDATE matches a row
        (Postgres row-level locking makes this a safe compare-and-swap; there
        is no separate SELECT-then-UPDATE window to race in). Returns the
        claimed row, or None if another worker already claimed it first (or
        it's in some other status entirely) — the caller must treat None as
        "someone else has this, safely exit", never as an error.

        expected_attempt, when given, additionally requires attempt_count to
        match — guards against an event for an OLD attempt (e.g. a slow
        redelivery from before a manual retry bumped attempt_count) resurrecting
        a recipient that has since moved on to a newer attempt.
        """
        stmt = (
            update(VoiceCampaignRecipient)
            .where(VoiceCampaignRecipient.id == recipient_id)
            .where(VoiceCampaignRecipient.status.in_(allowed_from))
        )
        if expected_attempt is not None:
            stmt = stmt.where(VoiceCampaignRecipient.attempt_count == expected_attempt)
        stmt = stmt.values(status="processing").returning(VoiceCampaignRecipient)
        res = await self.session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is not None:
            await self.session.flush()
        return row

    async def try_start_retry(
        self, recipient_id, *, campaign_id, allowed_from: list[str],
    ) -> VoiceCampaignRecipient | None:
        """Atomically bump attempt_count and reset status to 'queued' — the
        manual-retry equivalent of try_claim_for_processing. Same single
        UPDATE...WHERE...RETURNING shape: only a recipient currently in a
        retryable terminal status (FAILED/NO_ANSWER/BUSY, never COMPLETED —
        spec: 'retrying a successful recipient must not create another
        call') AND belonging to the given campaign_id is affected, and the
        row it returns already carries the NEW attempt_count the caller
        needs to derive the next execution_key."""
        stmt = (
            update(VoiceCampaignRecipient)
            .where(VoiceCampaignRecipient.id == recipient_id)
            .where(VoiceCampaignRecipient.campaign_id == campaign_id)
            .where(VoiceCampaignRecipient.status.in_(allowed_from))
            .values(
                status="queued",
                attempt_count=VoiceCampaignRecipient.attempt_count + 1,
                error_message=None,
            )
            .returning(VoiceCampaignRecipient)
        )
        res = await self.session.execute(stmt)
        row = res.scalar_one_or_none()
        if row is not None:
            await self.session.flush()
        return row

    async def get_by_id_unscoped(self, recipient_id) -> VoiceCampaignRecipient | None:
        """Worker-only: recipients carry no company_id column (see the
        module docstring — they're reached only through their tenant-scoped
        campaign), so a worker processing a Kafka event — which has no
        TenantContext — loads this row directly, then independently verifies
        campaign_id/company_id ownership from the DB before doing anything
        with it (never trusting the event payload alone)."""
        res = await self.session.execute(
            select(VoiceCampaignRecipient).where(VoiceCampaignRecipient.id == recipient_id)
        )
        return res.scalar_one_or_none()


class VoiceCampaignRecipientAttemptRepository:
    """Not a BaseRepository subclass: this table has no company_id at all
    (not even indirectly scoped the way recipients are) — it's pure
    execution history, always reached through an already-verified recipient.
    """

    def __init__(self, session):
        self.session = session

    async def try_claim(
        self, *, recipient_id, attempt_number: int, execution_key: str,
    ) -> VoiceCampaignRecipientAttempt | None:
        """Insert a new attempt row, guarded by execution_key's unique
        constraint via a SAVEPOINT (mirrors TtsUsageReservation.reserve()'s
        identical pattern from Phase 4A) — returns None if this exact
        execution_key was already claimed (duplicate Kafka delivery), so the
        caller can safely no-op rather than reprocess."""
        existing = await self.get_by_execution_key(execution_key)
        if existing is not None:
            return None
        attempt = VoiceCampaignRecipientAttempt(
            recipient_id=recipient_id, attempt_number=attempt_number,
            execution_key=execution_key, status="processing",
        )
        try:
            async with self.session.begin_nested():
                self.session.add(attempt)
                await self.session.flush()
        except IntegrityError:
            existing = await self.get_by_execution_key(execution_key)
            if existing is None:
                raise  # genuinely unexpected — surface the original error
            return None
        return attempt

    async def get_by_execution_key(self, execution_key: str) -> VoiceCampaignRecipientAttempt | None:
        res = await self.session.execute(
            select(VoiceCampaignRecipientAttempt).where(
                VoiceCampaignRecipientAttempt.execution_key == execution_key
            )
        )
        return res.scalar_one_or_none()

    async def update(self, attempt: VoiceCampaignRecipientAttempt, **data) -> VoiceCampaignRecipientAttempt:
        for field, value in data.items():
            setattr(attempt, field, value)
        await self.session.flush()
        return attempt

    async def list_for_recipient(self, recipient_id) -> Sequence[VoiceCampaignRecipientAttempt]:
        res = await self.session.execute(
            select(VoiceCampaignRecipientAttempt)
            .where(VoiceCampaignRecipientAttempt.recipient_id == recipient_id)
            .order_by(VoiceCampaignRecipientAttempt.attempt_number.asc())
        )
        return res.scalars().all()


class VoiceCampaignAudioRepository(BaseRepository[VoiceCampaignAudio]):
    # Same reasoning as recipients — reached only via campaign/recipient.
    model = VoiceCampaignAudio
    tenant_scoped = False

    async def get_for_recipient(self, recipient_id) -> VoiceCampaignAudio | None:
        res = await self.session.execute(
            select(VoiceCampaignAudio).where(
                VoiceCampaignAudio.recipient_id == recipient_id
            )
        )
        return res.scalar_one_or_none()
