"""Company data access.

Companies are the tenant roots, not tenant-scoped rows, so this repository
disables the base tenant scoping. Access control (super-admin only) is enforced
in the route layer via require_permission.
"""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.company import Company
from app.repositories.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    model = Company
    tenant_scoped = False  # companies are the tenants themselves

    async def get_by_slug(self, slug: str) -> Optional[Company]:
        stmt = select(Company).where(
            func.lower(Company.slug) == slug.lower(),
            Company.deleted_at.is_(None),
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def slug_exists(self, slug: str, exclude_id=None) -> bool:
        stmt = select(Company.id).where(
            func.lower(Company.slug) == slug.lower(),
            Company.deleted_at.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(Company.id != exclude_id)
        res = await self.session.execute(stmt)
        return res.first() is not None

    async def search(
        self,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        status=None,
        plan_id=None,
        sort_by: str = "created_at",
        sort_dir: str = "desc",
    ):
        """List companies with text search (name/slug), status/plan filters,
        and sorting. Excludes soft-deleted rows. Returns (rows, total).

        The plan relationship is selectin-loaded explicitly so list rows can
        expose the plan name in a single batched query (no per-row N+1)."""
        stmt = (
            select(Company)
            .where(Company.deleted_at.is_(None))
            .options(selectinload(Company.plan))
        )

        if search:
            term = f"%{search.lower()}%"
            stmt = stmt.where(
                func.lower(Company.name).like(term)
                | func.lower(Company.slug).like(term)
            )
        if status is not None:
            stmt = stmt.where(Company.status == status)
        if plan_id is not None:
            stmt = stmt.where(Company.plan_id == plan_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        sort_col = getattr(Company, sort_by, Company.created_at)
        stmt = stmt.order_by(
            sort_col.asc() if sort_dir == "asc" else sort_col.desc()
        ).offset(offset).limit(limit)

        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    async def list_plans(self):
        """Active subscription plans, ordered by name."""
        from app.models.subscription_plan import SubscriptionPlan

        stmt = (
            select(SubscriptionPlan)
            .where(SubscriptionPlan.is_active.is_(True))
            .order_by(SubscriptionPlan.name)
        )
        return (await self.session.execute(stmt)).scalars().all()