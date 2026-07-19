"""Telephony service (FreePBX / Asterisk integration layer).

Provider-managed model: PBX connections are platform-owned infrastructure,
managed by super admins only. Company admins never see or manage PBX config;
they consume telecom features (Voice, Missed Call, Campaigns) built on top of it.
Connections are platform-owned (company_id NULL).

The AMI secret is encrypted on write (app/core/crypto) and never returned. All
state changes are audited. Status tests run through the AsteriskProvider seam
(NullAsteriskProvider today), so they work without a real PBX.

Originate / event ingestion are intentionally NOT exposed here — they are the
provider seams that Voice (Phase 5) and Missed Call (Phase 6) will build on,
along with the repository's resolve_effective() per-tenant routing helper.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import TelephonyConnectionStatus
from app.core.crypto import encrypt_secret
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.models.telephony import TelephonyConnection
from app.repositories.telephony_repository import TelephonyConnectionRepository
from app.schemas.telephony import (
    ConnectionTestResult,
    TelephonyConnectionCreate,
    TelephonyConnectionUpdate,
)
from app.services.asterisk_provider import ConnectionParams, get_asterisk_provider
from app.services.audit_service import AuditService

_ENTITY = "telephony_connection"


class TelephonyService:
    def __init__(
        self, session: AsyncSession, repo: TelephonyConnectionRepository,
        audit: AuditService | None = None,
    ):
        self.session = session
        self.repo = repo
        self.ctx = repo.ctx
        self.audit = audit or AuditService(session)
        self.provider = get_asterisk_provider()

    @property
    def _company_id(self):
        return self.ctx.company_id if self.ctx else None

    @property
    def _is_super_admin(self) -> bool:
        return bool(self.ctx and self.ctx.is_super_admin)

    # ----- reads -----------------------------------------------------------
    async def list_connections(self):
        """All platform PBX connections (super-admin platform view)."""
        return list(await self.repo.list_all())

    async def get_connection(self, conn_id) -> TelephonyConnection:
        row = await self.repo.get_scoped(conn_id)
        if row is None:
            raise NotFoundError("Telephony connection not found")
        return row

    # ----- writes ----------------------------------------------------------
    async def create_connection(
        self, data: TelephonyConnectionCreate, *, actor_id=None, ip=None
    ) -> TelephonyConnection:
        # Provider-managed: PBX connections are platform-owned and super-admin
        # only. (Routes also enforce this; this is defense in depth.)
        if not self._is_super_admin:
            raise PermissionDeniedError(
                "Telephony connections are managed by platform administrators only"
            )
        # Platform-owned (company_id NULL). One platform connection is supported
        # by the integration layer; a duplicate is a conflict, not a silent
        # second row.
        if await self.repo.get_platform_default() is not None:
            raise ConflictError("A platform telephony connection already exists")
        company_id = None

        row = await self.repo.create(
            company_id=company_id,
            name=data.name,
            description=data.description,
            host=data.host,
            port=data.port,
            ami_username=data.ami_username,
            ami_secret_encrypted=encrypt_secret(data.ami_secret),
            use_tls=data.use_tls,
            enabled=data.enabled,
            last_status=TelephonyConnectionStatus.UNKNOWN.value,
            created_by=actor_id,
        )
        await self.audit.record(
            action="create", entity_type=_ENTITY, entity_id=row.id,
            actor_id=actor_id, company_id=company_id, ip_address=ip,
            new_values={"name": data.name, "host": data.host,
                        "platform_default": True},
        )
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def update_connection(
        self, conn_id, data: TelephonyConnectionUpdate, *, actor_id=None, ip=None
    ) -> TelephonyConnection:
        row = await self.get_connection(conn_id)
        patch: dict[str, Any] = {}
        for field in ("name", "description", "host", "port", "ami_username",
                      "use_tls", "enabled"):
            value = getattr(data, field)
            if value is not None:
                patch[field] = value
        if data.ami_secret is not None:
            patch["ami_secret_encrypted"] = encrypt_secret(data.ami_secret)
        if patch:
            await self.repo.update(row, **patch)
        await self.audit.record(
            action="update", entity_type=_ENTITY, entity_id=row.id,
            actor_id=actor_id, company_id=row.company_id, ip_address=ip,
            new_values={k: v for k, v in patch.items()
                        if k != "ami_secret_encrypted"} or {"secret": "rotated"},
        )
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def delete_connection(self, conn_id, *, actor_id=None, ip=None) -> None:
        row = await self.get_connection(conn_id)
        await self.repo.soft_delete(row)
        await self.audit.record(
            action="delete", entity_type=_ENTITY, entity_id=row.id,
            actor_id=actor_id, company_id=row.company_id, ip_address=ip,
        )
        await self.session.commit()

    # ----- live status -----------------------------------------------------
    async def test_connection(
        self, conn_id, *, actor_id=None, ip=None
    ) -> ConnectionTestResult:
        row = await self.get_connection(conn_id)
        result = await self._probe(row)
        await self.repo.update(
            row,
            last_status=(TelephonyConnectionStatus.CONNECTED.value
                         if result.connected
                         else TelephonyConnectionStatus.ERROR.value),
            last_checked_at=result.checked_at,
            last_error=None if result.connected else result.detail,
        )
        await self.session.commit()
        return result

    async def effective_status(self) -> tuple[str, Optional[TelephonyConnection],
                                              Optional[ConnectionTestResult]]:
        """Resolve the connection that would be used for the caller's company
        (hybrid) and probe it. Super admins probe the platform default."""
        company_id = self._company_id
        if self._is_super_admin:
            source = "platform-default"
            conn = await self.repo.get_platform_default()
        else:
            source, conn = await self.repo.resolve_effective(company_id)
        if conn is None:
            return "none", None, None
        status = await self._probe(conn)
        return source, conn, status

    async def _probe(self, row: TelephonyConnection) -> ConnectionTestResult:
        from app.core.config import settings
        from app.core.crypto import decrypt_secret
        now = datetime.now(timezone.utc)
        if not row.enabled:
            return ConnectionTestResult(
                connected=False, detail="Connection is disabled",
                provider=self.provider.name, checked_at=now,
            )
        try:
            secret = decrypt_secret(row.ami_secret_encrypted)
        except ValueError as exc:
            return ConnectionTestResult(
                connected=False, detail=str(exc),
                provider=self.provider.name, checked_at=now,
            )
        params = ConnectionParams(
            host=row.host, port=row.port, username=row.ami_username,
            secret=secret, use_tls=row.use_tls,
            timeout=settings.TELEPHONY_CONNECT_TIMEOUT,
        )
        status = await self.provider.get_status(params)
        return ConnectionTestResult(
            connected=status.connected, detail=status.detail,
            latency_ms=status.latency_ms, provider=status.provider or self.provider.name,
            checked_at=now,
        )
