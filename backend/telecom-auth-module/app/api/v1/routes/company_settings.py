"""Company Settings endpoints (Company Admin, self-scoped).

Every endpoint operates on the CALLER'S OWN company, taken from the
authenticated token (current_user.company_id) — never from a path or body. That
makes cross-tenant access structurally impossible: there is no company id in the
request to tamper with. Gated by company.read (which company_admin holds);
super admins have no company and get 404 here (they manage companies via the
platform /companies API instead).
"""
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Request,
    UploadFile,
    status,
)

from app.api.v1.deps import (
    CurrentUser,
    get_company_settings_service,
    require_permission,
)
from app.core.config import settings
from app.core.constants import Permission
from app.core.exceptions import ValidationError
from app.core.storage import get_storage
from app.schemas.change_request import ChangeRequestRead, SettingsUpdateResult
from app.schemas.company import CompanySettingsRead, CompanySettingsUpdate
from app.services.company_settings_service import CompanySettingsService

router = APIRouter(prefix="/company-settings", tags=["Company Settings"])

SettingsSvc = Annotated[
    CompanySettingsService, Depends(get_company_settings_service)
]
CanRead = Annotated[
    object, Depends(require_permission(Permission.COMPANY_READ.value))
]

_ALLOWED_LOGO_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/webp", "image/svg+xml",
}


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("", response_model=CompanySettingsRead)
async def get_company_settings(
    service: SettingsSvc, current_user: CurrentUser, _: CanRead,
) -> CompanySettingsRead:
    company = await service.get_own(current_user.company_id)
    return CompanySettingsRead.model_validate(company)


@router.patch("", response_model=SettingsUpdateResult)
async def update_company_settings(
    payload: CompanySettingsUpdate, service: SettingsSvc,
    current_user: CurrentUser, request: Request, _: CanRead,
) -> SettingsUpdateResult:
    _company, applied, pending = await service.update_own(
        current_user.company_id, payload,
        actor_id=current_user.id, ip=_client_ip(request),
    )
    return SettingsUpdateResult(
        immediate_applied=applied,
        pending_request=_to_request_read(pending) if pending else None,
    )


@router.get("/pending", response_model=ChangeRequestRead | None)
async def get_pending_change_request(
    service: SettingsSvc, current_user: CurrentUser, _: CanRead,
) -> ChangeRequestRead | None:
    # Surfaces the "approval pending" banner for the company admin.
    await service.get_own(current_user.company_id)  # tenant guard
    req = await service.change_requests.pending_for_company(
        current_user.company_id
    )
    return _to_request_read(req) if req else None


@router.post("/logo", response_model=CompanySettingsRead)
async def upload_company_logo(
    service: SettingsSvc, current_user: CurrentUser, request: Request,
    _: CanRead, file: UploadFile = File(...),
) -> CompanySettingsRead:
    if file.content_type not in _ALLOWED_LOGO_TYPES:
        raise ValidationError(
            "Logo must be a PNG, JPEG, WebP, or SVG image"
        )
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"Logo exceeds the {settings.MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit"
        )
    url = get_storage().save(
        data=data,
        filename=file.filename or "logo",
        content_type=file.content_type or "application/octet-stream",
        prefix=f"logos/{current_user.company_id}",
    )
    company = await service.set_logo(
        current_user.company_id, url,
        actor_id=current_user.id, ip=_client_ip(request),
    )
    return CompanySettingsRead.model_validate(company)


def _to_request_read(req) -> ChangeRequestRead:
    """Map a CompanyChangeRequest ORM row to its DTO, including the company and
    requester display names for the super-admin review screen."""
    return ChangeRequestRead(
        id=req.id,
        company_id=req.company_id,
        company_name=getattr(req.company, "name", None) if req.company else None,
        requested_by=req.requested_by,
        requester_name=(
            req.requester.full_name if getattr(req, "requester", None) else None
        ),
        status=req.status.value if hasattr(req.status, "value") else str(req.status),
        changes=req.changes,
        decision_reason=req.decision_reason,
        reviewed_at=req.reviewed_at,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )
