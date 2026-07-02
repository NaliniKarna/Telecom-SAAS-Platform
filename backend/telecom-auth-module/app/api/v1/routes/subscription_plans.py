"""Subscription plan management endpoints (platform-level; super-admin only).

Gated by the existing super-admin role check (require_role) — no new RBAC
permission is introduced. Plans are platform configuration owned by the
Super Admin.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.deps import CurrentUser, get_plan_service, require_role
from app.core.constants import RoleName
from app.schemas.common import PageMeta, PageParams
from app.schemas.subscription_plan import (
    PlanCreate,
    PlanFilter,
    PlanListItem,
    PlanRead,
    PlanUpdate,
)
from app.services.subscription_plan_service import SubscriptionPlanService

router = APIRouter(prefix="/subscription-plans", tags=["Subscription Plans"])

PlanDep = Annotated[SubscriptionPlanService, Depends(get_plan_service)]
SuperAdmin = Annotated[object, Depends(require_role(RoleName.SUPER_ADMIN.value))]


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=dict)
async def list_plans(
    service: PlanDep,
    _: SuperAdmin,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    is_active: bool | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
) -> dict:
    params = PageParams(page=page, size=size)
    filters = PlanFilter(
        search=search, is_active=is_active, sort_by=sort_by, sort_dir=sort_dir
    )
    rows, total, usage = await service.list_plans(
        offset=params.offset, limit=params.size, filters=filters
    )
    items = []
    for p in rows:
        item = PlanListItem.model_validate(p)
        item.usage_count = usage.get(p.id, 0)
        items.append(item)
    pages = (total + params.size - 1) // params.size
    return {
        "data": items,
        "meta": PageMeta(
            page=params.page, size=params.size, total=total, pages=pages
        ).model_dump(),
        "errors": [],
    }


@router.post("", response_model=PlanRead, status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: PlanCreate, service: PlanDep, current_user: CurrentUser,
    request: Request, _: SuperAdmin,
) -> PlanRead:
    plan = await service.create_plan(
        payload, actor_id=current_user.id, ip=_client_ip(request)
    )
    return PlanRead.model_validate(plan)


@router.get("/{plan_id}", response_model=dict)
async def get_plan(plan_id: uuid.UUID, service: PlanDep, _: SuperAdmin) -> dict:
    plan = await service.get_plan(plan_id)
    usage = await service.get_usage(plan_id)
    return {
        "data": PlanRead.model_validate(plan).model_dump(mode="json"),
        "usage_count": usage,
        "errors": [],
    }


@router.patch("/{plan_id}", response_model=PlanRead)
async def update_plan(
    plan_id: uuid.UUID, payload: PlanUpdate, service: PlanDep,
    current_user: CurrentUser, request: Request, _: SuperAdmin,
) -> PlanRead:
    plan = await service.update_plan(
        plan_id, payload, actor_id=current_user.id, ip=_client_ip(request)
    )
    return PlanRead.model_validate(plan)


@router.post("/{plan_id}/activate", response_model=PlanRead)
async def activate_plan(
    plan_id: uuid.UUID, service: PlanDep, current_user: CurrentUser,
    request: Request, _: SuperAdmin,
) -> PlanRead:
    plan = await service.set_active(
        plan_id, True, actor_id=current_user.id, ip=_client_ip(request)
    )
    return PlanRead.model_validate(plan)


@router.post("/{plan_id}/deactivate", response_model=PlanRead)
async def deactivate_plan(
    plan_id: uuid.UUID, service: PlanDep, current_user: CurrentUser,
    request: Request, _: SuperAdmin,
) -> PlanRead:
    plan = await service.set_active(
        plan_id, False, actor_id=current_user.id, ip=_client_ip(request)
    )
    return PlanRead.model_validate(plan)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(
    plan_id: uuid.UUID, service: PlanDep, current_user: CurrentUser,
    request: Request, _: SuperAdmin,
) -> None:
    await service.delete_plan(
        plan_id, actor_id=current_user.id, ip=_client_ip(request)
    )
