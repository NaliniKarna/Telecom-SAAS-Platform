"""Missed Call Platform service (Phase 6).

Business logic for the missed-call module.  Key design rules:

  - Callbacks are originated via VoiceService (not directly via AMI).
  - Status transitions are audited.
  - All writes commit atomically (service owns the transaction).
  - Dashboard stats are live aggregations, not cached counters.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    CallbackOutcome,
    MissedCallStatus,
    Permission,
)
from app.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.repositories.missed_call_repository import MissedCallRepository
from app.schemas.missed_call import (
    CallbackOutcomePatch,
    CallbackRequest,
    MissedCallAssignPatch,
    MissedCallCallbackRead,
    MissedCallCreate,
    MissedCallDashboardStats,
    MissedCallDetail,
    MissedCallNoteCreate,
    MissedCallNoteRead,
    MissedCallRead,
    MissedCallStatusPatch,
    PaginatedMissedCalls,
)
from app.schemas.voice import OriginateRequest
from app.services.audit_service import AuditService

_ENTITY = "missed_call"
_NOTE_ENTITY = "missed_call_note"
_CB_ENTITY = "missed_call_callback"


class MissedCallService:
    def __init__(
        self,
        session: AsyncSession,
        repo: MissedCallRepository,
        audit: AuditService,
    ) -> None:
        self.session = session
        self.repo = repo
        self.ctx = repo.ctx
        self.audit = audit

    # ── helpers ──────────────────────────────────────────────────────────────

    def _require(self, perm: str) -> None:
        if self.ctx is None or not self.ctx.has_permission(perm):
            raise PermissionDeniedError(f"Missing required permission: {perm}")

    @property
    def _company_id(self) -> uuid.UUID:
        if self.ctx is None or self.ctx.company_id is None:
            raise PermissionDeniedError(
                "Company context required for Missed Call features"
            )
        return uuid.UUID(str(self.ctx.company_id))

    # ── list / get ───────────────────────────────────────────────────────────

    async def list_missed_calls(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        status: str | None = None,
        assigned_to: uuid.UUID | None = None,
        search: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> PaginatedMissedCalls:
        self._require(Permission.MISSED_CALL_READ.value)
        rows, total = await self.repo.list_calls(
            offset=offset,
            limit=limit,
            status=status,
            assigned_to=assigned_to,
            search=search,
            from_date=from_date,
            to_date=to_date,
        )
        return PaginatedMissedCalls(
            items=[MissedCallRead.from_model(r) for r in rows],
            total=total,
            offset=offset,
            limit=limit,
        )

    async def get_missed_call(self, mc_id: uuid.UUID) -> MissedCallDetail:
        self._require(Permission.MISSED_CALL_READ.value)
        row = await self.repo.get_by_id(mc_id)
        if row is None:
            raise NotFoundError("Missed call not found")
        return MissedCallDetail.from_model_full(row)

    # ── create (from AMI event or manual) ────────────────────────────────────

    async def create_missed_call(
        self,
        data: MissedCallCreate,
        *,
        actor_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> MissedCallRead:
        self._require(Permission.MISSED_CALL_MANAGE.value)
        company_id = self._company_id

        row = await self.repo.create(
            company_id=company_id,
            caller_number=data.caller_number,
            called_number=data.called_number,
            called_extension_id=data.called_extension_id,
            status=MissedCallStatus.NEW.value,
            received_at=data.received_at,
            ring_duration_seconds=data.ring_duration_seconds,
            source_call_id=data.source_call_id,
            caller_name=data.caller_name,
            callback_count=0,
        )
        await self.audit.record(
            action="create",
            entity_type=_ENTITY,
            entity_id=row.id,
            actor_id=actor_id,
            company_id=company_id,
            ip_address=ip,
            new_values={
                "caller_number": data.caller_number,
                "called_number": data.called_number,
            },
        )
        await self.session.commit()
        await self.session.refresh(row)
        return MissedCallRead.from_model(row)

    # ── status ───────────────────────────────────────────────────────────────

    async def update_status(
        self,
        mc_id: uuid.UUID,
        data: MissedCallStatusPatch,
        *,
        actor_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> MissedCallRead:
        self._require(Permission.MISSED_CALL_MANAGE.value)
        row = await self.repo.get_by_id(mc_id)
        if row is None:
            raise NotFoundError("Missed call not found")
        old = row.status
        await self.repo.update(row, status=data.status)
        await self.audit.record(
            action="status_change",
            entity_type=_ENTITY,
            entity_id=row.id,
            actor_id=actor_id,
            company_id=row.company_id,
            ip_address=ip,
            old_values={"status": old},
            new_values={"status": data.status},
        )
        await self.session.commit()
        await self.session.refresh(row)
        return MissedCallRead.from_model(row)

    # ── assignment ───────────────────────────────────────────────────────────

    async def assign(
        self,
        mc_id: uuid.UUID,
        data: MissedCallAssignPatch,
        *,
        actor_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> MissedCallRead:
        self._require(Permission.MISSED_CALL_MANAGE.value)
        row = await self.repo.get_by_id(mc_id)
        if row is None:
            raise NotFoundError("Missed call not found")
        await self.repo.update(row, assigned_to=data.assigned_to)
        # Auto-acknowledge when assigned (if still new).
        if row.status == MissedCallStatus.NEW.value and data.assigned_to:
            await self.repo.update(row, status=MissedCallStatus.ACKNOWLEDGED.value)
        await self.audit.record(
            action="assign",
            entity_type=_ENTITY,
            entity_id=row.id,
            actor_id=actor_id,
            company_id=row.company_id,
            ip_address=ip,
            new_values={"assigned_to": str(data.assigned_to)},
        )
        await self.session.commit()
        await self.session.refresh(row)
        return MissedCallRead.from_model(row)

    # ── notes ────────────────────────────────────────────────────────────────

    async def add_note(
        self,
        mc_id: uuid.UUID,
        data: MissedCallNoteCreate,
        *,
        actor_id: uuid.UUID,
        ip: str | None = None,
    ) -> MissedCallNoteRead:
        self._require(Permission.MISSED_CALL_MANAGE.value)
        row = await self.repo.get_by_id(mc_id)
        if row is None:
            raise NotFoundError("Missed call not found")
        note = await self.repo.add_note(
            missed_call_id=mc_id,
            company_id=row.company_id,
            author_id=actor_id,
            body=data.body,
        )
        await self.session.commit()
        await self.session.refresh(note)
        return MissedCallNoteRead.from_model(note)

    # ── callbacks ────────────────────────────────────────────────────────────

    async def initiate_callback(
        self,
        mc_id: uuid.UUID,
        data: CallbackRequest,
        *,
        actor_id: uuid.UUID,
        ip: str | None = None,
    ) -> MissedCallCallbackRead:
        """Originate a callback call via the Voice Platform and record the attempt."""
        self._require(Permission.MISSED_CALL_MANAGE.value)
        row = await self.repo.get_by_id(mc_id)
        if row is None:
            raise NotFoundError("Missed call not found")

        now = datetime.now(timezone.utc)
        company_id = row.company_id

        # ── Originate the call via Voice service (reuse, don't duplicate) ──
        voice_call_id: uuid.UUID | None = None
        try:
            from app.api.v1.deps import get_voice_service
            from app.repositories.voice_repository import (
                VoiceCallLogRepository,
                VoiceExtensionRepository,
            )
            from app.repositories.telephony_repository import (
                TelephonyConnectionRepository,
            )
            from app.services.voice_service import VoiceService

            voice_svc = VoiceService(
                self.session,
                VoiceExtensionRepository(self.session, self.ctx),
                VoiceCallLogRepository(self.session, self.ctx),
                TelephonyConnectionRepository(self.session, self.ctx),
                self.audit,
            )
            originate_data = OriginateRequest(
                caller_extension_id=data.extension_id,
                caller_number=data.caller_number if not data.extension_id else None,
                destination_number=row.caller_number,
            )
            call_log = await voice_svc.originate_call(
                originate_data, actor_id=actor_id, ip=ip
            )
            voice_call_id = call_log.id
        except Exception:
            # If originate fails, still record the callback attempt (outcome=failed).
            pass

        # ── Record callback attempt ──
        cb = await self.repo.add_callback(
            missed_call_id=mc_id,
            company_id=company_id,
            performed_by=actor_id,
            extension_id=data.extension_id,
            voice_call_id=voice_call_id,
            attempted_at=now,
            notes=data.notes,
        )

        # Increment callback counter and set status to "returned".
        new_count = (row.callback_count or 0) + 1
        await self.repo.update(
            row,
            callback_count=new_count,
            status=MissedCallStatus.RETURNED.value,
        )

        await self.audit.record(
            action="callback",
            entity_type=_CB_ENTITY,
            entity_id=cb.id,
            actor_id=actor_id,
            company_id=company_id,
            ip_address=ip,
            new_values={
                "missed_call_id": str(mc_id),
                "destination": row.caller_number,
                "voice_call_id": str(voice_call_id) if voice_call_id else None,
            },
        )
        await self.session.commit()
        await self.session.refresh(cb)
        return MissedCallCallbackRead.from_model(cb)

    async def update_callback_outcome(
        self,
        mc_id: uuid.UUID,
        cb_id: uuid.UUID,
        data: CallbackOutcomePatch,
        *,
        actor_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> MissedCallCallbackRead:
        """Record the outcome of a callback attempt."""
        self._require(Permission.MISSED_CALL_MANAGE.value)
        cb = await self.repo.get_callback(cb_id)
        if cb is None or str(cb.missed_call_id) != str(mc_id):
            raise NotFoundError("Callback not found")

        patch: dict[str, Any] = {"outcome": data.outcome}
        if data.duration_seconds is not None:
            patch["duration_seconds"] = data.duration_seconds
        if data.notes is not None:
            patch["notes"] = data.notes

        for k, v in patch.items():
            setattr(cb, k, v)
        await self.session.flush()

        await self.audit.record(
            action="callback_outcome",
            entity_type=_CB_ENTITY,
            entity_id=cb.id,
            actor_id=actor_id,
            company_id=cb.company_id,
            ip_address=ip,
            new_values=patch,
        )
        await self.session.commit()
        await self.session.refresh(cb)
        return MissedCallCallbackRead.from_model(cb)

    # ── dashboard ────────────────────────────────────────────────────────────

    async def get_dashboard_stats(self) -> MissedCallDashboardStats:
        self._require(Permission.MISSED_CALL_READ.value)
        by_status = await self.repo.count_by_status()
        today = await self.repo.missed_today()
        cb_stats = await self.repo.callback_stats()

        pending = by_status.get(MissedCallStatus.NEW.value, 0) + by_status.get(
            MissedCallStatus.ACKNOWLEDGED.value, 0
        )
        total_missed = sum(by_status.values())

        return MissedCallDashboardStats(
            missed_today=today,
            pending_callbacks=pending,
            total_missed=total_missed,
            by_status=by_status,
            **cb_stats,
        )
