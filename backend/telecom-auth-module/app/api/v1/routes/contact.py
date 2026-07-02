"""Contact endpoints (Company Admin). Tenant-scoped via TenantContext.

Reads gated by contact.read; writes by contact.manage.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile, status

from app.api.v1.deps import (
    CurrentUser,
    get_contact_import_service,
    get_contact_service,
    require_permission,
)
from app.core.constants import ContactStatus, Permission
from app.core.exceptions import ValidationError
from app.models.contact import Contact
from app.schemas.contact import (
    ContactCreate,
    ContactFilter,
    ContactListItem,
    ContactRead,
    ContactUpdate,
    ImportCommitRequest,
    ImportCommitResponse,
    ImportPreviewResponse,
)
from app.services.contact_service import ContactService
from app.services.contact_import_service import ContactImportService

router = APIRouter(prefix="/contacts", tags=["Contacts"])

ContactSvc = Annotated[ContactService, Depends(get_contact_service)]
ImportSvc = Annotated[ContactImportService, Depends(get_contact_import_service)]
CanRead = Annotated[object, Depends(require_permission(Permission.CONTACT_READ.value))]
CanManage = Annotated[object, Depends(require_permission(Permission.CONTACT_MANAGE.value))]

_MAX_CSV_BYTES = 5 * 1024 * 1024  # 5 MB


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.get("", response_model=dict)
async def list_contacts(
    service: ContactSvc, _: CanRead,
    search: str | None = None,
    contact_status: ContactStatus | None = Query(default=None, alias="status"),
    tag: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> dict:
    flt = ContactFilter(search=search, status=contact_status, tag=tag)
    rows, total = await service.list_contacts(flt, offset=(page - 1) * size, limit=size)
    return {
        "data": [ContactListItem.model_validate(c).model_dump(mode="json") for c in rows],
        "meta": {"page": page, "size": size, "total": total,
                 "pages": (total + size - 1) // size},
    }


@router.post("", response_model=ContactRead, status_code=status.HTTP_201_CREATED)
async def create_contact(
    payload: ContactCreate, service: ContactSvc, current_user: CurrentUser,
    request: Request, _: CanManage,
) -> ContactRead:
    c = await service.create_contact(payload, actor_id=current_user.id, ip=_client_ip(request))
    return ContactRead.model_validate(c)


@router.get("/{contact_id}", response_model=ContactRead)
async def get_contact(
    contact_id: uuid.UUID, service: ContactSvc, _: CanRead,
) -> ContactRead:
    return ContactRead.model_validate(await service.get_contact(contact_id))


@router.patch("/{contact_id}", response_model=ContactRead)
async def update_contact(
    contact_id: uuid.UUID, payload: ContactUpdate, service: ContactSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
) -> ContactRead:
    c = await service.update_contact(contact_id, payload, actor_id=current_user.id, ip=_client_ip(request))
    return ContactRead.model_validate(c)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: uuid.UUID, service: ContactSvc, current_user: CurrentUser,
    request: Request, _: CanManage,
) -> None:
    await service.delete_contact(contact_id, actor_id=current_user.id, ip=_client_ip(request))


@router.post("/import/preview", response_model=ImportPreviewResponse)
async def import_preview(
    service: ImportSvc, _: CanManage,
    file: UploadFile = File(...),
) -> ImportPreviewResponse:
    """Parse + validate a CSV, returning per-row status (valid/invalid/duplicate).
    Writes nothing — the client reviews this before committing."""
    if file.content_type not in (
        "text/csv", "application/vnd.ms-excel", "application/octet-stream", "text/plain",
    ):
        raise ValidationError("Please upload a .csv file")
    data = await file.read()
    if len(data) > _MAX_CSV_BYTES:
        raise ValidationError("CSV exceeds the 5MB limit")
    return await service.preview(data)


@router.post("/import", response_model=ImportCommitResponse)
async def import_commit(
    payload: ImportCommitRequest, service: ImportSvc, current_user: CurrentUser,
    request: Request, _: CanManage,
) -> ImportCommitResponse:
    """Bulk-insert reviewed rows. Duplicates handled per `on_duplicate`
    (skip|import_anyway). Audited as a single contact/import event."""
    imported, skipped, failed, errors = await service.commit(
        payload, actor_id=current_user.id, ip=_client_ip(request)
    )
    return ImportCommitResponse(
        imported=imported, skipped_duplicates=skipped, failed=failed, errors=errors,
    )
