"""Company management endpoints (platform-level; super-admin only).

RBAC: every endpoint is gated by the existing require_permission guard on the
company.* permission codes (only super_admin holds the create/update/delete/
activate/deactivate permissions). Mutations capture actor + client IP for audit.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status

from app.api.v1.deps import (
    CurrentUser,
    get_company_service,
    get_user_management_service,
    require_permission,
)
from app.core.constants import CompanyStatus, Permission
from app.schemas.common import PageMeta, PageParams
from app.schemas.company import (
    CompanyCreate,
    CompanyFilter,
    CompanyListItem,
    CompanyRead,
    CompanyUpdate,
)
from app.schemas.subscription_plan import PlanRead
from app.services.company_service import CompanyService
from app.schemas.user import CompanyAdminInvite, UserRead
from app.services.email_service import EmailService
from app.services.user_management_service import UserManagementService
from app.repositories.subscription_plan import SubscriptionPlanRepository

router = APIRouter(prefix="/companies", tags=["Companies"])

CompanyDep = Annotated[CompanyService, Depends(get_company_service)]


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/plans", response_model=list[PlanRead])
async def list_plans_for_company_form(
    service: CompanyDep,
    _: Annotated[object, Depends(require_permission(Permission.COMPANY_READ.value))],
):
    """Active subscription plans, for the Company create/edit form's plan
    picker. MUST be registered before GET /{company_id} below — a dynamic
    path segment matches literally any string, including "plans", which
    previously fell through here as an (invalid) company_id and returned a
    misleading 422 instead of 404/200.
    """
    repo = SubscriptionPlanRepository(service.session)
    rows, _total, _usage = await repo.search(offset=0, limit=1000, is_active=True)
    return [PlanRead.model_validate(p) for p in rows]


@router.get("", response_model=dict)
async def list_companies(
    service: CompanyDep,
    _: Annotated[object, Depends(require_permission(Permission.COMPANY_READ.value))],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    status_filter: CompanyStatus | None = Query(None, alias="status"),
    plan_id: uuid.UUID | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
) -> dict:
    params = PageParams(page=page, size=size)
    filters = CompanyFilter(
        search=search, status=status_filter, plan_id=plan_id,
        sort_by=sort_by, sort_dir=sort_dir,
    )
    rows, total = await service.list_companies(
        offset=params.offset, limit=params.size, filters=filters
    )
    pages = (total + params.size - 1) // params.size
    return {
        "data": [CompanyListItem.model_validate(r) for r in rows],
        "meta": PageMeta(
            page=params.page, size=params.size, total=total, pages=pages
        ).model_dump(),
        "errors": [],
    }


@router.post("", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
async def create_company(
    payload: CompanyCreate,
    service: CompanyDep,
    current_user: CurrentUser,
    request: Request,
    _: Annotated[object, Depends(require_permission(Permission.COMPANY_CREATE.value))],
) -> CompanyRead:
    company = await service.create_company(
        payload, actor_id=current_user.id, ip=_client_ip(request)
    )
    return CompanyRead.model_validate(company)


@router.get("/{company_id}", response_model=CompanyRead)
async def get_company(
    company_id: uuid.UUID,
    service: CompanyDep,
    _: Annotated[object, Depends(require_permission(Permission.COMPANY_READ.value))],
) -> CompanyRead:
    company = await service.get_company(company_id)
    return CompanyRead.model_validate(company)


@router.patch("/{company_id}", response_model=CompanyRead)
async def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdate,
    service: CompanyDep,
    current_user: CurrentUser,
    request: Request,
    _: Annotated[object, Depends(require_permission(Permission.COMPANY_UPDATE.value))],
) -> CompanyRead:
    company = await service.update_company(
        company_id, payload, actor_id=current_user.id, ip=_client_ip(request)
    )
    return CompanyRead.model_validate(company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: uuid.UUID,
    service: CompanyDep,
    current_user: CurrentUser,
    request: Request,
    _: Annotated[object, Depends(require_permission(Permission.COMPANY_DELETE.value))],
) -> None:
    await service.delete_company(
        company_id, actor_id=current_user.id, ip=_client_ip(request)
    )


@router.post("/{company_id}/activate", response_model=CompanyRead)
async def activate_company(
    company_id: uuid.UUID,
    service: CompanyDep,
    current_user: CurrentUser,
    request: Request,
    _: Annotated[
        object, Depends(require_permission(Permission.COMPANY_ACTIVATE.value))
    ],
) -> CompanyRead:
    company = await service.activate_company(
        company_id, actor_id=current_user.id, ip=_client_ip(request)
    )
    return CompanyRead.model_validate(company)


@router.post("/{company_id}/deactivate", response_model=CompanyRead)
async def deactivate_company(
    company_id: uuid.UUID,
    service: CompanyDep,
    current_user: CurrentUser,
    request: Request,
    _: Annotated[
        object, Depends(require_permission(Permission.COMPANY_DEACTIVATE.value))
    ],
) -> CompanyRead:
    company = await service.deactivate_company(
        company_id, actor_id=current_user.id, ip=_client_ip(request)
    )
    return CompanyRead.model_validate(company)

@router.post("/{company_id}/suspend", response_model=CompanyRead)
async def suspend_company(
    company_id: uuid.UUID,
    service: CompanyDep,
    current_user: CurrentUser,
    request: Request,
    # Reuses company.deactivate permission (no RBAC change): suspend is a
    # turn-off action in the same privilege class as deactivate.
    _: Annotated[
        object, Depends(require_permission(Permission.COMPANY_DEACTIVATE.value))
    ],
) -> CompanyRead:
    company = await service.suspend_company(
        company_id, actor_id=current_user.id, ip=_client_ip(request)
    )
    return CompanyRead.model_validate(company)


@router.post(
    "/{company_id}/invite-admin",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
async def invite_company_admin(
    company_id: uuid.UUID,
    payload: CompanyAdminInvite,
    user_service: Annotated[
        UserManagementService, Depends(get_user_management_service)
    ],
    current_user: CurrentUser,
    request: Request,
    background: BackgroundTasks,
    # Super-admin platform action: gated by company.update (super_admin only).
    _: Annotated[
        object, Depends(require_permission(Permission.COMPANY_UPDATE.value))
    ],
) -> UserRead:
    """Bootstrap a company's first admin (or add another). Creates a PENDING
    company_admin in the target company and emails an invite to set a password."""
    user, token = await user_service.invite_company_admin(
        company_id, payload.email, payload.first_name, payload.last_name,
        actor_id=current_user.id, ip=_client_ip(request),
    )
    background.add_task(EmailService().send_invite, user.email, token)
    r = UserRead.model_validate(user)
    r.roles = user.role_names
    return r