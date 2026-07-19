"""Voice Platform repositories (Phase 5).

Both repositories are tenant-scoped (company_id from the request context).
Repositories return models or None; they never raise NotFound (that is the
service's job) and never commit (transactions belong to services).

VoiceExtensionRepository:
    Standard CRUD + agent-status lookup helpers.

VoiceCallLogRepository:
    CDR-optimised: active-call view, filtered history, analytics aggregations.
    NOTE: VoiceCallLog has no deleted_at column — CDRs are permanent records.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import and_, case, func, or_, select

from app.core.constants import ACTIVE_CALL_STATUSES, CallStatus
from app.models.voice import VoiceCallLog, VoiceExtension
from app.repositories.base import BaseRepository


class VoiceExtensionRepository(BaseRepository[VoiceExtension]):
    model = VoiceExtension
    tenant_scoped = True

    # BaseRepository._base_select() already applies company_id scope and
    # deleted_at IS NULL filter automatically.

    async def get_by_number(
        self, extension_number: str
    ) -> Optional[VoiceExtension]:
        """Look up a live extension by its dialable number (company-scoped)."""
        stmt = self._base_select().where(
            VoiceExtension.extension_number == extension_number
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_active(self) -> Sequence[VoiceExtension]:
        """All enabled, non-deleted extensions for the company."""
        stmt = (
            self._base_select()
            .where(VoiceExtension.enabled.is_(True))
            .order_by(VoiceExtension.extension_number.asc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def count_by_agent_status(self) -> dict[str, int]:
        """Aggregate extension counts by agent_status (for dashboard widget)."""
        stmt = (
            select(VoiceExtension.agent_status, func.count().label("n"))
            .where(
                VoiceExtension.company_id == self.ctx.company_id,
                VoiceExtension.deleted_at.is_(None),
                VoiceExtension.enabled.is_(True),
            )
            .group_by(VoiceExtension.agent_status)
        )
        rows = (await self.session.execute(stmt)).all()
        counts: dict[str, int] = {
            "available": 0, "busy": 0, "away": 0, "offline": 0,
        }
        for status, n in rows:
            if status in counts:
                counts[status] = n
        return counts


class VoiceCallLogRepository(BaseRepository[VoiceCallLog]):
    model = VoiceCallLog
    tenant_scoped = True

    # VoiceCallLog has no deleted_at — override _apply_soft_delete to be a no-op.
    def _apply_soft_delete(self, stmt):
        return stmt  # CDRs are permanent

    # ---- reads -------------------------------------------------------------

    async def list_calls(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        direction: str | None = None,
        status: str | None = None,
        extension_id: uuid.UUID | None = None,
        search: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> tuple[Sequence[VoiceCallLog], int]:
        """CDR history with optional filters, paginated."""
        stmt = self._base_select()

        if direction:
            stmt = stmt.where(VoiceCallLog.direction == direction)
        if status:
            stmt = stmt.where(VoiceCallLog.status == status)
        if extension_id:
            stmt = stmt.where(
                or_(
                    VoiceCallLog.caller_extension_id == extension_id,
                    VoiceCallLog.callee_extension_id == extension_id,
                )
            )
        if search:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    VoiceCallLog.caller_number.ilike(pattern),
                    VoiceCallLog.callee_number.ilike(pattern),
                )
            )
        if from_date:
            stmt = stmt.where(VoiceCallLog.started_at >= from_date)
        if to_date:
            stmt = stmt.where(VoiceCallLog.started_at <= to_date)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.offset(offset)
            .limit(limit)
            .order_by(VoiceCallLog.started_at.desc())
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    async def list_active(self) -> Sequence[VoiceCallLog]:
        """Calls that are currently in progress (not yet ended)."""
        stmt = (
            self._base_select()
            .where(
                VoiceCallLog.ended_at.is_(None),
                VoiceCallLog.status.in_(list(ACTIVE_CALL_STATUSES)),
            )
            .order_by(VoiceCallLog.started_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def count_active(self) -> int:
        stmt = (
            select(func.count())
            .where(
                VoiceCallLog.company_id == self.ctx.company_id,
                VoiceCallLog.ended_at.is_(None),
                VoiceCallLog.status.in_(list(ACTIVE_CALL_STATUSES)),
            )
        )
        return (await self.session.execute(stmt)).scalar_one()

    # ---- analytics aggregations --------------------------------------------

    async def overview_stats(self) -> dict[str, Any]:
        """Aggregate stats for the Voice overview dashboard widget."""
        stmt = select(
            func.count().label("total"),
            func.sum(
                case((VoiceCallLog.status == CallStatus.ANSWERED.value, 1), else_=0)
            ).label("answered"),
            func.sum(
                case((VoiceCallLog.status == CallStatus.COMPLETED.value, 1), else_=0)
            ).label("completed"),
            func.sum(
                case(
                    (VoiceCallLog.status.in_([
                        CallStatus.FAILED.value,
                        CallStatus.BUSY.value,
                        CallStatus.NO_ANSWER.value,
                    ]), 1),
                    else_=0,
                )
            ).label("failed"),
            func.sum(
                case(
                    (VoiceCallLog.direction == "outbound", 1), else_=0
                )
            ).label("outbound"),
            func.sum(
                case(
                    (VoiceCallLog.direction == "inbound", 1), else_=0
                )
            ).label("inbound"),
            func.coalesce(
                func.sum(VoiceCallLog.duration_seconds), 0
            ).label("total_duration"),
            func.coalesce(
                func.avg(VoiceCallLog.duration_seconds), 0.0
            ).label("avg_duration"),
        ).where(VoiceCallLog.company_id == self.ctx.company_id)

        row = (await self.session.execute(stmt)).one()
        total = row.total or 0
        answered = (row.answered or 0) + (row.completed or 0)
        return {
            "total_calls": total,
            "answered_calls": answered,
            "answer_rate_pct": round(answered / total * 100, 1) if total else 0.0,
            "avg_duration_seconds": round(float(row.avg_duration or 0), 1),
            "total_duration_seconds": int(row.total_duration or 0),
            "outbound_calls": int(row.outbound or 0),
            "inbound_calls": int(row.inbound or 0),
            "failed_calls": int(row.failed or 0),
        }

    async def timeseries(self, *, days: int = 30) -> list[dict[str, Any]]:
        """Daily call counts for the last `days` days (analytics chart)."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        date_trunc = func.date_trunc("day", VoiceCallLog.started_at)

        stmt = (
            select(
                date_trunc.label("day"),
                func.count().label("total"),
                func.sum(
                    case(
                        (VoiceCallLog.status.in_([
                            CallStatus.ANSWERED.value,
                            CallStatus.COMPLETED.value,
                        ]), 1),
                        else_=0,
                    )
                ).label("answered"),
                func.sum(
                    case(
                        (VoiceCallLog.status.in_([
                            CallStatus.FAILED.value,
                            CallStatus.BUSY.value,
                            CallStatus.NO_ANSWER.value,
                        ]), 1),
                        else_=0,
                    )
                ).label("failed"),
            )
            .where(
                VoiceCallLog.company_id == self.ctx.company_id,
                VoiceCallLog.started_at >= since,
            )
            .group_by(date_trunc)
            .order_by(date_trunc.asc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            {
                "date": r.day.date().isoformat(),
                "total": r.total,
                "answered": int(r.answered or 0),
                "failed": int(r.failed or 0),
            }
            for r in rows
        ]
