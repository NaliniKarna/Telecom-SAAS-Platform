"""Dashboard endpoints.

- /dashboard/overview         platform-wide, super-admin only
- /dashboard/company-overview tenant-scoped, for the company workspace
"""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.v1.deps import (
    CurrentUser,
    get_company_dashboard_service,
    get_dashboard_service,
    require_permission,
    require_role,
)
from app.core.constants import Permission, RoleName
from app.schemas.company_dashboard import CompanyDashboardOverview
from app.schemas.dashboard import DashboardOverview
from app.services.company_dashboard_service import CompanyDashboardService
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

DashDep = Annotated[DashboardService, Depends(get_dashboard_service)]
CompanyDashDep = Annotated[
    CompanyDashboardService, Depends(get_company_dashboard_service)
]
SuperAdmin = Annotated[object, Depends(require_role(RoleName.SUPER_ADMIN.value))]
CanReadStats = Annotated[
    object, Depends(require_permission(Permission.STATS_READ.value))
]


@router.get("/overview", response_model=DashboardOverview)
async def dashboard_overview(service: DashDep, _: SuperAdmin) -> DashboardOverview:
    return await service.overview()


@router.get("/company-overview", response_model=CompanyDashboardOverview)
async def company_dashboard_overview(
    service: CompanyDashDep, current_user: CurrentUser, _: CanReadStats,
) -> CompanyDashboardOverview:
    # Tenant-scoped: always the caller's own company, taken from the token.
    return await service.overview(current_user.company_id)
