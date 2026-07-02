"""Repositories for the SMS Foundation (sender IDs + templates).

Tenant isolation comes from BaseRepository (every query is filtered by the
request context's company_id; super admins bypass narrowing). The sender-ID
review helpers below deliberately span tenants for the super-admin approval
queue, mirroring the change-request workflow.

Campaign/message repositories are intentionally NOT part of the Foundation.
"""
from typing import Optional, Sequence

from sqlalchemy import func, or_, select

from app.core.constants import SenderApprovalStatus
from app.models.company import Company
from app.models.sms import SmsSenderId, SmsTemplate
from app.repositories.base import BaseRepository


class SmsSenderIdRepository(BaseRepository[SmsSenderId]):
    model = SmsSenderId
    tenant_scoped = True

    async def search(
        self, *, search: str | None = None, status=None, approval_status=None,
        offset: int = 0, limit: int = 20,
    ) -> tuple[Sequence[SmsSenderId], int]:
        stmt = self._base_select()
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(
                SmsSenderId.name.ilike(like),
                SmsSenderId.sender_id.ilike(like),
                SmsSenderId.description.ilike(like),
            ))
        if status is not None:
            stmt = stmt.where(SmsSenderId.status == status)
        if approval_status is not None:
            stmt = stmt.where(SmsSenderId.approval_status == approval_status)

        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = stmt.order_by(SmsSenderId.created_at.desc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    async def get_by_value(self, sender_id_value: str) -> Optional[SmsSenderId]:
        """Find a sender by its string value within the current tenant."""
        stmt = self._base_select().where(SmsSenderId.sender_id == sender_id_value)
        return (await self.session.execute(stmt.limit(1))).scalars().first()

    async def clear_default(self) -> None:
        """Unset is_default on the company's current default(s) before setting a
        new one (keeps the one-default-per-company invariant)."""
        stmt = self._base_select().where(SmsSenderId.is_default.is_(True))
        for row in (await self.session.execute(stmt)).scalars().all():
            row.is_default = False
        await self.session.flush()

    # ----- super-admin review (cross-tenant by design) ----------------------
    async def list_pending_all_companies(
        self, *, search: str | None = None, offset: int = 0, limit: int = 20,
    ) -> tuple[Sequence[tuple[SmsSenderId, str | None]], int]:
        """SUPER-ADMIN ONLY. Pending sender IDs across every company, with the
        company name joined for display. Bypasses tenant scope deliberately;
        callers are role-gated to super_admin."""
        where = [
            SmsSenderId.approval_status == SenderApprovalStatus.PENDING,
            SmsSenderId.deleted_at.is_(None),
        ]
        if search:
            like = f"%{search}%"
            where.append(or_(
                SmsSenderId.name.ilike(like), SmsSenderId.sender_id.ilike(like),
            ))
        base = (
            select(SmsSenderId, Company.name)
            .join(Company, Company.id == SmsSenderId.company_id, isouter=True)
            .where(*where)
        )
        total = (await self.session.execute(
            select(func.count()).select_from(
                select(SmsSenderId.id).where(*where).subquery()
            )
        )).scalar_one()
        rows = (await self.session.execute(
            base.order_by(SmsSenderId.created_at.asc()).offset(offset).limit(limit)
        )).all()
        return rows, total

    async def get_any_company(self, sender_pk) -> Optional[SmsSenderId]:
        """SUPER-ADMIN ONLY. Fetch by PK ignoring tenant scope, for review."""
        stmt = select(SmsSenderId).where(
            SmsSenderId.id == sender_pk, SmsSenderId.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class SmsTemplateRepository(BaseRepository[SmsTemplate]):
    model = SmsTemplate
    tenant_scoped = True

    async def search(
        self, *, search: str | None = None, status=None,
        offset: int = 0, limit: int = 20,
    ) -> tuple[Sequence[SmsTemplate], int]:
        stmt = self._base_select()
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(
                SmsTemplate.name.ilike(like), SmsTemplate.body.ilike(like),
            ))
        if status is not None:
            stmt = stmt.where(SmsTemplate.status == status)

        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = stmt.order_by(SmsTemplate.created_at.desc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total
