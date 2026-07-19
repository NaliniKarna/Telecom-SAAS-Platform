"""Telephony connection repository.

tenant_scoped=False because this table is platform-owned infrastructure, not
per-tenant data. Scope is enforced explicitly here + by super-admin-only route
guards:

  - PBX connections are provider-managed (super admin only). Platform-owned
    rows have company_id NULL.
  - `resolve_effective()` implements a hybrid-capable rule (a company's own
    enabled connection if one exists, else the platform default). Company-scoped
    rows aren't created in the provider-managed model today, but the resolver is
    kept for Voice / Missed-Call (Phase 5/6) per-tenant routing.
"""
from __future__ import annotations

import uuid
from typing import Optional, Sequence

from sqlalchemy import select

from app.models.telephony import TelephonyConnection
from app.repositories.base import BaseRepository


class TelephonyConnectionRepository(BaseRepository[TelephonyConnection]):
    model = TelephonyConnection
    tenant_scoped = False  # platform-owned; explicit scoping (see docstring)

    def _live(self):
        return select(TelephonyConnection).where(
            TelephonyConnection.deleted_at.is_(None)
        )

    async def list_all(self) -> Sequence[TelephonyConnection]:
        """All live connections (super-admin platform view)."""
        stmt = self._live().order_by(TelephonyConnection.created_at.desc())
        return (await self.session.execute(stmt)).scalars().all()

    async def get_scoped(self, conn_id: uuid.UUID) -> Optional[TelephonyConnection]:
        """Fetch a row the caller is allowed to touch. Super admins (the only
        telephony managers) may touch any row; company callers only their own."""
        stmt = self._live().where(TelephonyConnection.id == conn_id)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        if self.ctx is None or self.ctx.is_super_admin:
            return row
        # Company callers: only their own company's rows.
        if str(row.company_id) == str(self.ctx.company_id):
            return row
        return None

    async def list_for_company(self) -> Sequence[TelephonyConnection]:
        """Company's own connection rows."""
        stmt = (
            self._live()
            .where(TelephonyConnection.company_id == self.ctx.company_id)
            .order_by(TelephonyConnection.created_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().all()

    async def get_platform_default(self) -> Optional[TelephonyConnection]:
        stmt = self._live().where(TelephonyConnection.company_id.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_company_connection(
        self, company_id
    ) -> Optional[TelephonyConnection]:
        stmt = self._live().where(
            TelephonyConnection.company_id == company_id,
            TelephonyConnection.enabled.is_(True),
        ).order_by(TelephonyConnection.created_at.desc())
        return (await self.session.execute(stmt)).scalars().first()

    async def resolve_effective(
        self, company_id
    ) -> tuple[str, Optional[TelephonyConnection]]:
        """Hybrid resolution. Returns (source, connection):
        ("company", row) | ("platform-default", row) | ("none", None)."""
        if company_id is not None:
            own = await self.get_company_connection(company_id)
            if own is not None:
                return "company", own
        default = await self.get_platform_default()
        if default is not None and default.enabled:
            return "platform-default", default
        return "none", None
