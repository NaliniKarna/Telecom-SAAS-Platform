"""Company self-registration endpoints.

- POST /registration                     PUBLIC — submit a company registration.
- GET  /registration/pending             super admin — review queue.
- POST /registration/{company_id}/approve  super admin — approve (-> ACTIVE).
- POST /registration/{company_id}/reject   super admin — reject (-> REJECTED).

Access control is unchanged from the rest of the platform: the review endpoints
use the existing super-admin role guard, and approval simply flips the company
(and its admin) to ACTIVE — the existing login gate does the enforcement.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from app.api.v1.deps import (
    CurrentUser,
    get_registration_service,
    require_role,
)
from app.core.constants import RoleName
from app.schemas.registration import (
    CompanyRegistrationRequest,
    PendingRegistration,
    RegistrationDecision,
    RegistrationResult,
)
from app.services.email_service import EmailService
from app.services.registration_service import RegistrationService

router = APIRouter(prefix="/registration", tags=["Registration"])

RegSvc = Annotated[RegistrationService, Depends(get_registration_service)]
IsSuperAdmin = Annotated[object, Depends(require_role(RoleName.SUPER_ADMIN.value))]


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post(
    "", response_model=RegistrationResult, status_code=status.HTTP_201_CREATED
)
async def register_company(
    payload: CompanyRegistrationRequest,
    service: RegSvc,
    request: Request,
    background: BackgroundTasks,
) -> RegistrationResult:
    """Public: create a company registration request. The company is created in
    PENDING_APPROVAL and the admin in PENDING; an email-verification link is sent.
    Approval by a super admin (after email verification) grants access."""
    _company, user, token = await service.register_company(
        payload, ip=_client_ip(request)
    )
    background.add_task(EmailService().send_email_verification, user.email, token)
    return RegistrationResult()


@router.get("/pending", response_model=list[PendingRegistration])
async def list_pending(service: RegSvc, _: IsSuperAdmin) -> list[PendingRegistration]:
    rows = await service.list_pending()
    return [
        PendingRegistration(
            company_id=c.id,
            company_name=c.name,
            slug=c.slug,
            status=c.status.value,
            contact_phone=c.contact_phone,
            admin_user_id=(admin.id if admin else None),
            admin_email=(admin.email if admin else None),
            admin_name=(admin.full_name if admin else None),
            admin_email_verified=(admin.is_email_verified if admin else False),
            submitted_at=c.created_at,
        )
        for c, admin in rows
    ]


@router.post("/{company_id}/approve", response_model=PendingRegistration)
async def approve_registration(
    company_id: uuid.UUID, service: RegSvc, current_user: CurrentUser,
    request: Request, _: IsSuperAdmin,
) -> PendingRegistration:
    company = await service.approve(
        company_id, reviewer_id=current_user.id, ip=_client_ip(request)
    )
    admin = await service._admin_of(company)
    return PendingRegistration(
        company_id=company.id, company_name=company.name, slug=company.slug,
        status=company.status.value, contact_phone=company.contact_phone,
        admin_user_id=(admin.id if admin else None),
        admin_email=(admin.email if admin else None),
        admin_name=(admin.full_name if admin else None),
        admin_email_verified=(admin.is_email_verified if admin else False),
        submitted_at=company.created_at,
    )


@router.post("/{company_id}/reject", response_model=PendingRegistration)
async def reject_registration(
    company_id: uuid.UUID, payload: RegistrationDecision, service: RegSvc,
    current_user: CurrentUser, request: Request, _: IsSuperAdmin,
) -> PendingRegistration:
    company = await service.reject(
        company_id, reviewer_id=current_user.id, reason=payload.reason,
        ip=_client_ip(request),
    )
    return PendingRegistration(
        company_id=company.id, company_name=company.name, slug=company.slug,
        status=company.status.value, contact_phone=company.contact_phone,
        submitted_at=company.created_at,
    )
