"""Voice Platform service (Phase 5).

Business logic layer for the Voice module.  This service:
  - Manages the VoiceExtension registry (CRUD + agent-status).
  - Orchestrates outbound calls through the AsteriskProvider seam.
  - Persists call records (CDR) in VoiceCallLog.
  - Provides analytics aggregations over CDR data.

Design rules (mirrored from TelephonyService):
  - Never import a concrete AMI client or touch AMI directly.
  - Use get_asterisk_provider() to obtain the active provider.
  - Use TelephonyConnectionRepository.resolve_effective() for per-tenant
    connection resolution.
  - All writes are audited; commits belong to this layer.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import (
    AgentStatus,
    CallDirection,
    CallStatus,
    Permission,
)
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.models.voice import VoiceCallLog, VoiceExtension
from app.repositories.telephony_repository import TelephonyConnectionRepository
from app.repositories.voice_repository import (
    VoiceCallLogRepository,
    VoiceExtensionRepository,
)
from app.schemas.voice import (
    AgentStatusPatch,
    CallStatusPatch,
    ExtensionStatusSummary,
    OriginateRequest,
    PaginatedCallLogs,
    TimeseriesPoint,
    VoiceCallLogRead,
    VoiceExtensionCreate,
    VoiceExtensionRead,
    VoiceExtensionUpdate,
    VoiceOverviewStats,
    VoiceTimeseriesStats,
)
from app.services.asterisk_provider import ConnectionParams, get_asterisk_provider
from app.services.audit_service import AuditService

_EXT_ENTITY = "voice_extension"
_CALL_ENTITY = "voice_call_log"


class VoiceService:
    def __init__(
        self,
        session: AsyncSession,
        ext_repo: VoiceExtensionRepository,
        call_repo: VoiceCallLogRepository,
        telephony_repo: TelephonyConnectionRepository,
        audit: AuditService,
    ) -> None:
        self.session = session
        self.ext_repo = ext_repo
        self.call_repo = call_repo
        self.telephony_repo = telephony_repo
        self.audit = audit
        self.ctx = ext_repo.ctx
        self.provider = get_asterisk_provider()

    # ── helpers ──────────────────────────────────────────────────────────────

    def _require_permission(self, perm: str) -> None:
        if self.ctx is None or not self.ctx.has_permission(perm):
            raise PermissionDeniedError(f"Missing required permission: {perm}")

    @property
    def _company_id(self) -> uuid.UUID:
        if self.ctx is None or self.ctx.company_id is None:
            raise PermissionDeniedError("Company context required for Voice features")
        return uuid.UUID(str(self.ctx.company_id))

    # ── Extension CRUD ────────────────────────────────────────────────────────

    async def list_extensions(
        self, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[VoiceExtensionRead], int]:
        self._require_permission(Permission.VOICE_READ.value)
        rows, total = await self.ext_repo.list(offset=offset, limit=limit)
        return [VoiceExtensionRead.from_model(r) for r in rows], total

    async def get_extension(self, ext_id: uuid.UUID) -> VoiceExtensionRead:
        self._require_permission(Permission.VOICE_READ.value)
        row = await self.ext_repo.get_by_id(ext_id)
        if row is None:
            raise NotFoundError("Extension not found")
        return VoiceExtensionRead.from_model(row)

    async def create_extension(
        self,
        data: VoiceExtensionCreate,
        *,
        actor_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> VoiceExtensionRead:
        self._require_permission(Permission.VOICE_MANAGE.value)
        company_id = self._company_id

        # Uniqueness guard (partial index does the DB enforcement, this gives
        # a clean conflict error before hitting the DB constraint).
        existing = await self.ext_repo.get_by_number(data.extension_number)
        if existing is not None:
            raise ConflictError(
                f"Extension {data.extension_number!r} already exists for this company"
            )

        row = await self.ext_repo.create(
            company_id=company_id,
            extension_number=data.extension_number,
            display_name=data.display_name,
            description=data.description,
            context=data.context,
            technology=data.technology,
            enabled=data.enabled,
            user_id=data.user_id,
            agent_status=AgentStatus.OFFLINE.value,
        )
        await self.audit.record(
            action="create",
            entity_type=_EXT_ENTITY,
            entity_id=row.id,
            actor_id=actor_id,
            company_id=company_id,
            ip_address=ip,
            new_values={
                "extension_number": data.extension_number,
                "display_name": data.display_name,
            },
        )
        await self.session.commit()
        await self.session.refresh(row)
        return VoiceExtensionRead.from_model(row)

    async def update_extension(
        self,
        ext_id: uuid.UUID,
        data: VoiceExtensionUpdate,
        *,
        actor_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> VoiceExtensionRead:
        self._require_permission(Permission.VOICE_MANAGE.value)
        row = await self.ext_repo.get_by_id(ext_id)
        if row is None:
            raise NotFoundError("Extension not found")

        patch: dict[str, Any] = {}
        for field in ("display_name", "description", "context", "technology",
                      "enabled", "user_id"):
            value = getattr(data, field)
            if value is not None:
                patch[field] = value
        # user_id=None is a valid "unassign" — handle explicitly.
        if "user_id" not in patch and data.user_id is None and hasattr(data, "user_id"):
            patch["user_id"] = None

        if patch:
            await self.ext_repo.update(row, **patch)
        await self.audit.record(
            action="update",
            entity_type=_EXT_ENTITY,
            entity_id=row.id,
            actor_id=actor_id,
            company_id=row.company_id,
            ip_address=ip,
            new_values=patch or {"no_change": True},
        )
        await self.session.commit()
        await self.session.refresh(row)
        return VoiceExtensionRead.from_model(row)

    async def delete_extension(
        self,
        ext_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> None:
        self._require_permission(Permission.VOICE_MANAGE.value)
        row = await self.ext_repo.get_by_id(ext_id)
        if row is None:
            raise NotFoundError("Extension not found")
        await self.ext_repo.soft_delete(row)
        await self.audit.record(
            action="delete",
            entity_type=_EXT_ENTITY,
            entity_id=row.id,
            actor_id=actor_id,
            company_id=row.company_id,
            ip_address=ip,
        )
        await self.session.commit()

    async def update_agent_status(
        self,
        ext_id: uuid.UUID,
        data: AgentStatusPatch,
        *,
        actor_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> VoiceExtensionRead:
        """Update real-time presence for an extension."""
        self._require_permission(Permission.VOICE_READ.value)
        row = await self.ext_repo.get_by_id(ext_id)
        if row is None:
            raise NotFoundError("Extension not found")
        await self.ext_repo.update(
            row,
            agent_status=data.agent_status,
            last_seen_at=datetime.now(timezone.utc),
        )
        await self.session.commit()
        await self.session.refresh(row)
        return VoiceExtensionRead.from_model(row)

    # ── Outbound calls ────────────────────────────────────────────────────────

    async def originate_call(
        self,
        data: OriginateRequest,
        *,
        actor_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> VoiceCallLogRead:
        """Initiate an outbound voice call via the active AsteriskProvider.

        Resolution order for the A-leg channel:
          1. caller_extension_id → look up extension, use channel_string.
          2. caller_number → raw number (trunk-style originate).
        The B-leg is always data.destination_number.
        The effective PBX connection is resolved per-tenant (own → platform default).
        """
        self._require_permission(Permission.VOICE_DIAL.value)
        company_id = self._company_id
        now = datetime.now(timezone.utc)

        # --- Resolve A-leg ---
        caller_ext: VoiceExtension | None = None
        caller_number: str

        if data.caller_extension_id:
            caller_ext = await self.ext_repo.get_by_id(data.caller_extension_id)
            if caller_ext is None:
                raise NotFoundError("Caller extension not found")
            if not caller_ext.enabled:
                raise ValidationError("Caller extension is disabled")
            channel = caller_ext.channel_string
            caller_number = caller_ext.extension_number
        elif data.caller_number:
            channel = f"PJSIP/{data.caller_number}"
            caller_number = data.caller_number
        else:
            raise ValidationError(
                "Provide either caller_extension_id or caller_number"
            )

        # --- Resolve PBX connection ---
        source, conn = await self.telephony_repo.resolve_effective(company_id)
        connection_id: uuid.UUID | None = None

        if conn is not None and conn.enabled:
            connection_id = conn.id
            from app.core.crypto import decrypt_secret
            try:
                secret = decrypt_secret(conn.ami_secret_encrypted)
            except ValueError:
                secret = ""  # NullProvider ignores it; real provider will fail

            from app.core.config import settings
            params = ConnectionParams(
                host=conn.host,
                port=conn.port,
                username=conn.ami_username,
                secret=secret,
                use_tls=conn.use_tls,
                timeout=settings.TELEPHONY_CONNECT_TIMEOUT,
            )
            result = await self.provider.originate(
                params,
                channel=channel,
                extension=data.destination_number,
                caller_id=data.caller_id_override or caller_number,
                context=caller_ext.context if caller_ext else "from-internal",
            )
        else:
            # No connection configured — still create the call log (dry-run /
            # simulation without any PBX; NullProvider accepts by design).
            from app.services.asterisk_provider import NullAsteriskProvider
            null_params = ConnectionParams(
                host="localhost", port=5038,
                username="sim", secret="sim",
            )
            result = await NullAsteriskProvider().originate(
                null_params,
                channel=channel,
                extension=data.destination_number,
            )

        if not result.accepted:
            raise ValidationError(
                f"Call originate rejected by provider: {result.error or 'unknown error'}"
            )

        # --- Persist CDR ---
        log = await self.call_repo.create(
            company_id=company_id,
            connection_id=connection_id,
            direction=CallDirection.OUTBOUND.value,
            status=CallStatus.INITIATED.value,
            caller_number=caller_number,
            callee_number=data.destination_number,
            caller_extension_id=caller_ext.id if caller_ext else None,
            callee_extension_id=None,
            started_at=now,
            action_id=result.action_id,
            context=caller_ext.context if caller_ext else "from-internal",
            initiated_by=actor_id,
        )

        await self.audit.record(
            action="originate",
            entity_type=_CALL_ENTITY,
            entity_id=log.id,
            actor_id=actor_id,
            company_id=company_id,
            ip_address=ip,
            new_values={
                "direction": "outbound",
                "caller": caller_number,
                "destination": data.destination_number,
                "action_id": result.action_id,
            },
        )
        await self.session.commit()
        await self.session.refresh(log)
        return VoiceCallLogRead.from_model(log)

    # ── CDR reads ─────────────────────────────────────────────────────────────

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
    ) -> PaginatedCallLogs:
        self._require_permission(Permission.VOICE_READ.value)
        rows, total = await self.call_repo.list_calls(
            offset=offset,
            limit=limit,
            direction=direction,
            status=status,
            extension_id=extension_id,
            search=search,
            from_date=from_date,
            to_date=to_date,
        )
        return PaginatedCallLogs(
            items=[VoiceCallLogRead.from_model(r) for r in rows],
            total=total,
            offset=offset,
            limit=limit,
        )

    async def get_active_calls(self) -> list[VoiceCallLogRead]:
        self._require_permission(Permission.VOICE_READ.value)
        rows = await self.call_repo.list_active()
        return [VoiceCallLogRead.from_model(r) for r in rows]

    async def get_call(self, call_id: uuid.UUID) -> VoiceCallLogRead:
        self._require_permission(Permission.VOICE_READ.value)
        row = await self.call_repo.get_by_id(call_id)
        if row is None:
            raise NotFoundError("Call record not found")
        return VoiceCallLogRead.from_model(row)

    async def update_call_status(
        self,
        call_id: uuid.UUID,
        data: CallStatusPatch,
        *,
        actor_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> VoiceCallLogRead:
        """Update a call's lifecycle status.

        In production this is driven by AMI events; in simulation mode (Null
        provider) it can be called manually from the UI to move a call through
        its lifecycle (answer → complete → hangup).
        """
        self._require_permission(Permission.VOICE_MANAGE.value)
        row = await self.call_repo.get_by_id(call_id)
        if row is None:
            raise NotFoundError("Call record not found")

        patch: dict[str, Any] = {"status": data.status}
        now = datetime.now(timezone.utc)

        if data.status == CallStatus.ANSWERED.value and row.answered_at is None:
            patch["answered_at"] = now
        if data.status in (
            CallStatus.COMPLETED.value,
            CallStatus.BUSY.value,
            CallStatus.FAILED.value,
            CallStatus.NO_ANSWER.value,
            CallStatus.CANCELLED.value,
        ):
            patch["ended_at"] = now
            if row.answered_at and data.status == CallStatus.COMPLETED.value:
                patch["duration_seconds"] = int(
                    (now - row.answered_at).total_seconds()
                )
        if data.hangup_cause:
            patch["hangup_cause"] = data.hangup_cause

        await self.call_repo.update(row, **patch)
        await self.session.commit()
        await self.session.refresh(row)
        return VoiceCallLogRead.from_model(row)

    async def hangup_call(
        self,
        call_id: uuid.UUID,
        *,
        actor_id: uuid.UUID | None = None,
        ip: str | None = None,
    ) -> VoiceCallLogRead:
        """Mark a call as completed / cancelled (simulation hangup)."""
        row = await self.call_repo.get_by_id(call_id)
        if row is None:
            raise NotFoundError("Call record not found")
        if row.ended_at is not None:
            raise ValidationError("Call has already ended")

        now = datetime.now(timezone.utc)
        final_status = (
            CallStatus.COMPLETED.value
            if row.answered_at
            else CallStatus.CANCELLED.value
        )
        duration = (
            int((now - row.answered_at).total_seconds()) if row.answered_at else None
        )
        await self.call_repo.update(
            row,
            status=final_status,
            ended_at=now,
            duration_seconds=duration,
            hangup_cause="NORMAL_CLEARING",
        )
        await self.session.commit()
        await self.session.refresh(row)
        return VoiceCallLogRead.from_model(row)

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_overview_stats(self) -> VoiceOverviewStats:
        self._require_permission(Permission.VOICE_READ.value)
        active = await self.call_repo.count_active()
        stats = await self.call_repo.overview_stats()
        return VoiceOverviewStats(active_calls=active, **stats)

    async def get_timeseries(self, *, days: int = 30) -> VoiceTimeseriesStats:
        self._require_permission(Permission.VOICE_READ.value)
        points_raw = await self.call_repo.timeseries(days=days)
        return VoiceTimeseriesStats(
            points=[TimeseriesPoint(**p) for p in points_raw],
            period_days=days,
        )

    async def get_extension_status_summary(self) -> ExtensionStatusSummary:
        self._require_permission(Permission.VOICE_READ.value)
        counts = await self.ext_repo.count_by_agent_status()
        total = sum(counts.values())
        return ExtensionStatusSummary(total=total, **counts)
