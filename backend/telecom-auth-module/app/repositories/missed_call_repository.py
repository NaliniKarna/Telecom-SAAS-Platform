"""Missed Call Platform repository (Phase 6).

MissedCallRepository is tenant-scoped.  MissedCall has no deleted_at column
(missed calls are permanent records, like CDRs), so _apply_soft_delete is a
no-op.  Notes and callbacks are fetched via the ORM relationship (eager loaded)
rather than a separate repository class.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import and_, case, func, or_, select

from app.core.constants import CallbackOutcome, MissedCallStatus
from app.models.missed_call import MissedCall, MissedCallCallback, MissedCallNote
from app.repositories.base import BaseRepository


class MissedCallRepository(BaseRepository[MissedCall]):
    model = MissedCall
    tenant_scoped = True

    # MissedCall has no deleted_at — permanent records.
    def _apply_soft_delete(self, stmt):
        return stmt

    # ── reads ────────────────────────────────────────────────────────────────

    async def list_calls(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: str | None = None,
        assigned_to: uuid.UUID | None = None,
        search: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> tuple[Sequence[MissedCall], int]:
        stmt = self._base_select()

        if status:
            stmt = stmt.where(MissedCall.status == status)
        if assigned_to:
            stmt = stmt.where(MissedCall.assigned_to == assigned_to)
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    MissedCall.caller_number.ilike(pattern),
                    MissedCall.called_number.ilike(pattern),
                    MissedCall.caller_name.ilike(pattern),
                )
            )
        if from_date:
            stmt = stmt.where(MissedCall.received_at >= from_date)
        if to_date:
            stmt = stmt.where(MissedCall.received_at <= to_date)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.offset(offset)
            .limit(limit)
            .order_by(MissedCall.received_at.desc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    async def count_new(self) -> int:
        """Count of status='new' missed calls for this company (badge count)."""
        stmt = (
            select(func.count())
            .where(
                MissedCall.company_id == self.ctx.company_id,
                MissedCall.status == MissedCallStatus.NEW.value,
            )
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def count_by_status(self) -> dict[str, int]:
        stmt = (
            select(MissedCall.status, func.count().label("n"))
            .where(MissedCall.company_id == self.ctx.company_id)
            .group_by(MissedCall.status)
        )
        rows = (await self.session.execute(stmt)).all()
        counts: dict[str, int] = {s.value: 0 for s in MissedCallStatus}
        for status, n in rows:
            counts[status] = n
        return counts

    async def missed_today(self) -> int:
        start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        stmt = (
            select(func.count())
            .where(
                MissedCall.company_id == self.ctx.company_id,
                MissedCall.received_at >= start,
            )
        )
        return (await self.session.execute(stmt)).scalar_one()

    # ── callback analytics ───────────────────────────────────────────────────

    async def callback_stats(self) -> dict[str, Any]:
        """Aggregations for the missed-call dashboard: callback counts and
        average callback response time."""
        stmt = select(
            func.count().label("total"),
            func.sum(
                case(
                    (MissedCallCallback.outcome == CallbackOutcome.ANSWERED.value, 1),
                    else_=0,
                )
            ).label("answered"),
        ).where(MissedCallCallback.company_id == self.ctx.company_id)

        row = (await self.session.execute(stmt)).one()
        total = int(row.total or 0)
        answered = int(row.answered or 0)

        # Average time from missed_call.received_at to first callback attempt.
        avg_stmt = (
            select(
                func.avg(
                    func.extract(
                        "epoch",
                        MissedCallCallback.attempted_at - MissedCall.received_at,
                    )
                ).label("avg_response")
            )
            .join(
                MissedCall,
                MissedCallCallback.missed_call_id == MissedCall.id,
            )
            .where(MissedCallCallback.company_id == self.ctx.company_id)
        )
        avg_response = (await self.session.execute(avg_stmt)).scalar_one()

        return {
            "total_callbacks": total,
            "callbacks_answered": answered,
            "callback_success_rate_pct": (
                round(answered / total * 100, 1) if total else 0.0
            ),
            "avg_callback_time_seconds": round(float(avg_response or 0), 1),
        }

    # ── note / callback creates (no separate repo) ──────────────────────────

    async def add_note(
        self, *, missed_call_id: uuid.UUID, company_id: uuid.UUID,
        author_id: uuid.UUID, body: str,
    ) -> MissedCallNote:
        note = MissedCallNote(
            missed_call_id=missed_call_id,
            company_id=company_id,
            author_id=author_id,
            body=body,
        )
        self.session.add(note)
        await self.session.flush()
        return note

    async def add_callback(
        self, *, missed_call_id: uuid.UUID, company_id: uuid.UUID,
        performed_by: uuid.UUID, extension_id: uuid.UUID | None,
        voice_call_id: uuid.UUID | None, attempted_at: datetime,
        notes: str | None = None,
    ) -> MissedCallCallback:
        cb = MissedCallCallback(
            missed_call_id=missed_call_id,
            company_id=company_id,
            performed_by=performed_by,
            extension_id=extension_id,
            voice_call_id=voice_call_id,
            attempted_at=attempted_at,
            notes=notes,
        )
        self.session.add(cb)
        await self.session.flush()
        return cb

    async def get_callback(
        self, callback_id: uuid.UUID
    ) -> Optional[MissedCallCallback]:
        stmt = (
            select(MissedCallCallback)
            .where(
                MissedCallCallback.id == callback_id,
                MissedCallCallback.company_id == self.ctx.company_id,
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()
