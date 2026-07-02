"""Change Requests endpoints (super-admin only).

The super-admin review queue for gated company-settings changes (name,
contact_email, contact_phone). Also exposes a read-only "recent activity" feed
of immediate-save settings changes (address/timezone/logo) so the platform
admin stays aware of changes that didn't require approval.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy import desc, select

from app.api.v1.deps import (
    CurrentUser,
    DbSession,
    get_change_request_service,
    require_role,
)
from app.api.v1.routes.company_settings import _to_request_read
from app.core.constants import RoleName
from app.models.audit_log import AuditLog
from app.models.company import Company
from app.schemas.change_request import ChangeRequestRead, ReviewDecision
from app.services.change_request_service import ChangeRequestService

router = APIRouter(prefix="/change-requests", tags=["Change Requests"])

CRSvc = Annotated[ChangeRequestService, Depends(get_change_request_service)]
SuperAdmin = Annotated[
    object, Depends(require_role(RoleName.SUPER_ADMIN.value))
]


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("", response_model=list[ChangeRequestRead])
async def list_pending(service: CRSvc, _: SuperAdmin) -> list[ChangeRequestRead]:
    reqs = await service.list_pending()
    return [_to_request_read(r) for r in reqs]


@router.post("/{request_id}/approve", response_model=ChangeRequestRead)
async def approve_request(
    request_id, service: CRSvc, current_user: CurrentUser,
    request: Request, _: SuperAdmin,
) -> ChangeRequestRead:
    req = await service.approve(
        request_id, reviewer_id=current_user.id, ip=_client_ip(request)
    )
    return _to_request_read(req)


@router.post("/{request_id}/reject", response_model=ChangeRequestRead)
async def reject_request(
    request_id, payload: ReviewDecision, service: CRSvc,
    current_user: CurrentUser, request: Request, _: SuperAdmin,
) -> ChangeRequestRead:
    req = await service.reject(
        request_id, reviewer_id=current_user.id,
        reason=payload.reason, ip=_client_ip(request),
    )
    return _to_request_read(req)


@router.get("/recent-activity", response_model=list[dict])
async def recent_activity(
    db: DbSession, _: SuperAdmin, limit: int = 15,
) -> list[dict]:
    """Immediate-save company-settings changes (address/timezone/logo), newest
    first, with the company name resolved. Read-only awareness feed."""
    rows = (await db.execute(
        select(AuditLog, Company.name)
        .join(Company, Company.id == AuditLog.company_id, isouter=True)
        .where(
            AuditLog.entity_type == "company_settings",
            AuditLog.action.in_(["update", "update_logo"]),
        )
        .order_by(desc(AuditLog.created_at))
        .limit(min(limit, 50))
    )).all()
    out = []
    for log, company_name in rows:
        out.append({
            "id": str(log.id),
            "company_id": str(log.company_id) if log.company_id else None,
            "company_name": company_name,
            "action": log.action,
            "changed_fields": list((log.new_values or {}).keys()),
            "new_values": log.new_values,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })
    return out
