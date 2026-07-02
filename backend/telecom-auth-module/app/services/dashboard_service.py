"""Dashboard aggregation service (read-only platform overview).

Computes KPIs and feeds for the Super Admin dashboard from existing tables
(companies, subscription_plans, audit_logs). All queries exclude soft-deleted
rows. Kept deliberately small and query-driven so it stays cheap as data grows.
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.constants import CompanyStatus
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.models.subscription_plan import SubscriptionPlan
from app.models.user import User
from app.schemas.dashboard import (
    DashboardKpis,
    DashboardOverview,
    PlanDistribution,
    RecentActivity,
    RecentCompany,
)


class DashboardService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def overview(
        self, *, recent_limit: int = 5, activity_limit: int = 10
    ) -> DashboardOverview:
        return DashboardOverview(
            kpis=await self._kpis(),
            recent_companies=await self._recent_companies(recent_limit),
            recent_activity=await self._recent_activity(activity_limit),
            plan_distribution=await self._plan_distribution(),
        )

    async def _kpis(self) -> DashboardKpis:
        # Company counts grouped by status in one query.
        rows = (await self.session.execute(
            select(Company.status, func.count())
            .where(Company.deleted_at.is_(None))
            .group_by(Company.status)
        )).all()
        by_status = {s: n for s, n in rows}

        def count_for(status: CompanyStatus) -> int:
            # status may come back as enum or raw value depending on driver.
            return int(
                by_status.get(status)
                or by_status.get(status.value)
                or 0
            )

        total = sum(int(n) for _, n in rows)
        total_plans = (await self.session.execute(
            select(func.count()).select_from(SubscriptionPlan)
            .where(SubscriptionPlan.deleted_at.is_(None))
        )).scalar_one()

        return DashboardKpis(
            total_companies=total,
            active_companies=count_for(CompanyStatus.ACTIVE),
            suspended_companies=count_for(CompanyStatus.SUSPENDED),
            deactivated_companies=count_for(CompanyStatus.DEACTIVATED),
            total_plans=int(total_plans),
        )

    async def _recent_companies(self, limit: int) -> list[RecentCompany]:
        plan = aliased(SubscriptionPlan)
        rows = (await self.session.execute(
            select(Company, plan.name.label("plan_name"))
            .select_from(Company)
            .outerjoin(plan, Company.plan_id == plan.id)
            .where(Company.deleted_at.is_(None))
            .order_by(Company.created_at.desc())
            .limit(limit)
        )).all()
        out: list[RecentCompany] = []
        for company, plan_name in rows:
            item = RecentCompany.model_validate(company)
            item.status = (
                company.status.value
                if hasattr(company.status, "value")
                else str(company.status)
            )
            item.plan_name = plan_name
            out.append(item)
        return out

    async def _recent_activity(self, limit: int) -> list[RecentActivity]:
        actor = aliased(User)
        comp = aliased(Company)
        rows = (await self.session.execute(
            select(
                AuditLog,
                actor.email, actor.first_name, actor.last_name,
                comp.name.label("company_name"),
            )
            .select_from(AuditLog)
            .outerjoin(actor, AuditLog.actor_id == actor.id)
            .outerjoin(comp, AuditLog.company_id == comp.id)
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )).all()
        out: list[RecentActivity] = []
        for log, email, first, last, company_name in rows:
            name = " ".join(filter(None, [first, last])) or email
            out.append(RecentActivity(
                id=log.id, action=log.action, entity_type=log.entity_type,
                actor_name=name, company_name=company_name,
                created_at=log.created_at,
            ))
        return out

    async def _plan_distribution(self) -> list[PlanDistribution]:
        """Company count per plan. Includes plans with zero companies and an
        'Unassigned' bucket for companies without a plan."""
        # counts per assigned plan
        counts = dict((await self.session.execute(
            select(Company.plan_id, func.count())
            .where(Company.deleted_at.is_(None))
            .group_by(Company.plan_id)
        )).all())

        plans = (await self.session.execute(
            select(SubscriptionPlan)
            .where(SubscriptionPlan.deleted_at.is_(None))
            .order_by(SubscriptionPlan.name)
        )).scalars().all()

        dist = [
            PlanDistribution(
                plan_id=p.id, plan_name=p.name,
                company_count=int(counts.get(p.id, 0)),
            )
            for p in plans
        ]
        unassigned = int(counts.get(None, 0))
        if unassigned:
            dist.append(PlanDistribution(
                plan_id=None, plan_name="Unassigned", company_count=unassigned
            ))
        return dist
