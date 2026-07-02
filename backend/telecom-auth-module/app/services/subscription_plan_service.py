"""Subscription plan management use cases.

Owns transaction boundaries and business rules:
- unique code and name (case-insensitive),
- plans assigned to companies cannot be deleted,
- usage count surfaced on reads.
Records an audit entry for every mutating action on the same transaction.
"""
import logging
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.subscription_plan import SubscriptionPlan
from app.repositories.subscription_plan import SubscriptionPlanRepository
from app.schemas.subscription_plan import PlanCreate, PlanFilter, PlanUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_ENTITY = "subscription_plan"


class SubscriptionPlanService:
    def __init__(
        self,
        session: AsyncSession,
        repo: SubscriptionPlanRepository,
        audit: AuditService | None = None,
    ):
        self.session = session
        self.plans = repo
        self.audit = audit or AuditService(session)

    # ----- reads ------------------------------------------------------------
    async def list_plans(
        self, *, offset: int, limit: int, filters: PlanFilter | None = None
    ) -> tuple[Sequence[SubscriptionPlan], int, dict]:
        f = filters or PlanFilter()
        return await self.plans.search(
            offset=offset, limit=limit, search=f.search,
            is_active=f.is_active, sort_by=f.sort_by, sort_dir=f.sort_dir,
        )

    async def get_plan(self, plan_id) -> SubscriptionPlan:
        plan = await self.plans.get_by_id(plan_id)
        if plan is None or plan.deleted_at is not None:
            raise NotFoundError("Subscription plan not found")
        return plan

    async def get_usage(self, plan_id) -> int:
        return await self.plans.usage_count(plan_id)

    # ----- mutations --------------------------------------------------------
    async def create_plan(
        self, data: PlanCreate, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> SubscriptionPlan:
        if await self.plans.code_exists(data.code):
            raise ConflictError(f"A plan with code '{data.code}' already exists")
        if await self.plans.name_exists(data.name):
            raise ConflictError(f"A plan with name '{data.name}' already exists")
        fields = data.model_dump()
        fields["created_by"] = actor_id
        fields["updated_by"] = actor_id
        plan = await self.plans.create(**fields)
        await self.audit.record(
            action="create", entity_type=_ENTITY, entity_id=plan.id,
            actor_id=actor_id, ip_address=ip,
            new_values={"code": plan.code, "name": plan.name},
        )
        await self.session.commit()
        await self.session.refresh(plan)
        return plan

    async def update_plan(
        self, plan_id, data: PlanUpdate, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> SubscriptionPlan:
        plan = await self.get_plan(plan_id)
        patch = data.model_dump(exclude_unset=True)
        if "name" in patch and await self.plans.name_exists(
            patch["name"], exclude_id=plan.id
        ):
            raise ConflictError(f"A plan with name '{patch['name']}' already exists")
        if patch:
            before = {k: getattr(plan, k) for k in patch}
            patch["updated_by"] = actor_id
            await self.plans.update(plan, **patch)
            await self.audit.record(
                action="update", entity_type=_ENTITY, entity_id=plan.id,
                actor_id=actor_id, ip_address=ip,
                old_values=_jsonable(before), new_values=_jsonable(patch),
            )
            await self.session.commit()
            await self.session.refresh(plan)
        return plan

    async def set_active(
        self, plan_id, active: bool, *, actor_id=None, ip=None
    ) -> SubscriptionPlan:
        plan = await self.get_plan(plan_id)
        if plan.is_active != active:
            await self.plans.update(plan, is_active=active, updated_by=actor_id)
            await self.audit.record(
                action="activate" if active else "deactivate",
                entity_type=_ENTITY, entity_id=plan.id, actor_id=actor_id,
                ip_address=ip, new_values={"is_active": active},
            )
            await self.session.commit()
            await self.session.refresh(plan)
        return plan

    async def delete_plan(
        self, plan_id, *, actor_id=None, ip=None
    ) -> None:
        plan = await self.get_plan(plan_id)
        usage = await self.plans.usage_count(plan_id)
        if usage > 0:
            raise ValidationError(
                f"Cannot delete: {usage} company(ies) are assigned this plan. "
                "Reassign them first."
            )
        await self.plans.soft_delete(plan)
        await self.audit.record(
            action="delete", entity_type=_ENTITY, entity_id=plan_id,
            actor_id=actor_id, ip_address=ip,
        )
        await self.session.commit()


def _jsonable(d: dict) -> dict:
    """Coerce non-JSON values (UUIDs etc.) to str for the audit JSONB columns."""
    out = {}
    for k, v in d.items():
        out[k] = v if isinstance(v, (str, int, float, bool, type(None))) else str(v)
    return out
