"""Audit log query endpoints (platform-wide read).

Gated to the super-admin role (platform-wide trail; never tenant-visible). Read-only;
the audit trail is append-only and written by AuditService elsewhere.
"""
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import get_audit_log_service, require_role
from app.core.constants import RoleName
from app.schemas.audit_log import AuditFacets, AuditLogFilter
from app.schemas.common import PageMeta, PageParams
from app.services.audit_log_service import AuditLogService

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])

AuditDep = Annotated[AuditLogService, Depends(get_audit_log_service)]
# Platform-wide audit trail is a super-admin tool only. company_admin also
# holds audit.read in RBAC, so gating on the permission would let a tenant read
# EVERY company's audit log — a cross-tenant leak. Lock to the super-admin role.
CanRead = Annotated[
    object, Depends(require_role(RoleName.SUPER_ADMIN.value))
]


@router.get("", response_model=dict)
async def list_audit_logs(
    service: AuditDep,
    _: CanRead,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    company_id: uuid.UUID | None = Query(None),
    actor_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None, max_length=100),
    entity_type: str | None = Query(None, max_length=100),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
) -> dict:
    params = PageParams(page=page, size=size)
    filters = AuditLogFilter(
        search=search, company_id=company_id, actor_id=actor_id,
        action=action, entity_type=entity_type,
        date_from=date_from, date_to=date_to, sort_dir=sort_dir,
    )
    items, total = await service.list_logs(
        offset=params.offset, limit=params.size, filters=filters
    )
    pages = (total + params.size - 1) // params.size
    return {
        "data": [i.model_dump(mode="json") for i in items],
        "meta": PageMeta(
            page=params.page, size=params.size, total=total, pages=pages
        ).model_dump(),
        "errors": [],
    }


@router.get("/facets", response_model=AuditFacets)
async def audit_facets(service: AuditDep, _: CanRead) -> AuditFacets:
    """Distinct actions and modules, for filter dropdowns."""
    return await service.facets()
