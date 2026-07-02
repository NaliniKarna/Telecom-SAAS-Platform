"""Subscription plan data access.

Platform-level catalog (not tenant-scoped). Provides search/filter, uniqueness
checks for code/name, and company usage counts (how many companies reference
each plan) — used for the list view and to block deletion of in-use plans.
"""
from typing import Optional

from sqlalchemy import func, select

from app.models.company import Company
from app.models.subscription_plan import SubscriptionPlan
from app.repositories.base import BaseRepository


class SubscriptionPlanRepository(BaseRepository[SubscriptionPlan]):
    model = SubscriptionPlan
    tenant_scoped = False

    async def code_exists(self, code: str, exclude_id=None) -> bool:
        stmt = select(SubscriptionPlan.id).where(
            func.lower(SubscriptionPlan.code) == code.lower(),
            SubscriptionPlan.deleted_at.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(SubscriptionPlan.id != exclude_id)
        return (await self.session.execute(stmt)).first() is not None

    async def name_exists(self, name: str, exclude_id=None) -> bool:
        stmt = select(SubscriptionPlan.id).where(
            func.lower(SubscriptionPlan.name) == name.lower(),
            SubscriptionPlan.deleted_at.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(SubscriptionPlan.id != exclude_id)
        return (await self.session.execute(stmt)).first() is not None

    async def usage_count(self, plan_id) -> int:
        """How many (non-deleted) companies reference this plan."""
        stmt = select(func.count()).select_from(Company).where(
            Company.plan_id == plan_id, Company.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def search(
        self, *, offset: int, limit: int, search: Optional[str] = None,
        is_active: Optional[bool] = None, sort_by: str = "created_at",
        sort_dir: str = "desc",
    ):
        """Returns (rows, total, usage_by_id). Excludes soft-deleted plans."""
        stmt = select(SubscriptionPlan).where(
            SubscriptionPlan.deleted_at.is_(None)
        )
        if search:
            term = f"%{search.lower()}%"
            stmt = stmt.where(
                func.lower(SubscriptionPlan.name).like(term)
                | func.lower(SubscriptionPlan.code).like(term)
            )
        if is_active is not None:
            stmt = stmt.where(SubscriptionPlan.is_active.is_(is_active))

        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()

        sort_col = getattr(SubscriptionPlan, sort_by, SubscriptionPlan.created_at)
        stmt = stmt.order_by(
            sort_col.asc() if sort_dir == "asc" else sort_col.desc()
        ).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()

        # Usage counts for the page in one grouped query.
        ids = [p.id for p in rows]
        usage: dict = {}
        if ids:
            ucount = await self.session.execute(
                select(Company.plan_id, func.count())
                .where(Company.plan_id.in_(ids), Company.deleted_at.is_(None))
                .group_by(Company.plan_id)
            )
            usage = {pid: n for pid, n in ucount.all()}
        return rows, total, usage
