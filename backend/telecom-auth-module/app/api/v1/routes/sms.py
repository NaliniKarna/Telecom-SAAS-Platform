"""SMS Foundation endpoints: sender IDs + templates.

RBAC:
  - reads  -> sms.read
  - writes -> sms.manage
  - sender-ID approval/rejection -> super_admin role (company admins cannot
    self-approve), mirroring the company change-request workflow.

Campaign, message-sending, and analytics endpoints are intentionally NOT part
of this module.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.deps import (
    CurrentUser,
    get_sms_service,
    require_permission,
    require_role,
)
from app.core.constants import (
    Permission,
    RoleName,
    SenderApprovalStatus,
    SenderStatus,
    SmsTemplateStatus,
)
from app.schemas.sms import (
    ReviewDecision,
    SenderIdCreate,
    SenderIdRead,
    SenderIdReviewItem,
    SenderIdUpdate,
    TemplateCreate,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateRead,
    TemplateUpdate,
)
from app.services.sms_service import SmsService

router = APIRouter(prefix="/sms", tags=["SMS"])

SmsSvc = Annotated[SmsService, Depends(get_sms_service)]
CanRead = Annotated[object, Depends(require_permission(Permission.SMS_READ.value))]
CanManage = Annotated[object, Depends(require_permission(Permission.SMS_MANAGE.value))]
IsSuperAdmin = Annotated[object, Depends(require_role(RoleName.SUPER_ADMIN.value))]


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _page(rows, total, page, size, schema):
    return {
        "data": [schema.model_validate(r).model_dump(mode="json") for r in rows],
        "meta": {"page": page, "size": size, "total": total,
                 "pages": (total + size - 1) // size if size else 0},
    }


# ===================================================================== #
# Sender IDs — super-admin approval queue
# NOTE: these specific routes are declared BEFORE the parameterized
# "/sender-ids/{sender_id}" routes so they are not shadowed by the UUID path.
# ===================================================================== #
@router.get("/sender-ids/pending", response_model=dict)
async def list_pending_sender_ids(
    service: SmsSvc, _: IsSuperAdmin,
    search: str | None = None,
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
):
    rows, total = await service.list_pending_sender_ids(
        search=search, offset=(page - 1) * size, limit=size)
    data = []
    for sender, company_name in rows:
        item = SenderIdReviewItem.model_validate(sender)
        item.company_name = company_name
        data.append(item.model_dump(mode="json"))
    return {"data": data, "meta": {"page": page, "size": size, "total": total,
                                   "pages": (total + size - 1) // size if size else 0}}


@router.post("/sender-ids/{sender_id}/approve", response_model=SenderIdRead)
async def approve_sender_id(sender_id: uuid.UUID, service: SmsSvc,
                            current_user: CurrentUser, request: Request, _: IsSuperAdmin):
    return SenderIdRead.model_validate(
        await service.approve_sender_id(sender_id, reviewer_id=current_user.id,
                                        ip=_client_ip(request)))


@router.post("/sender-ids/{sender_id}/reject", response_model=SenderIdRead)
async def reject_sender_id(sender_id: uuid.UUID, payload: ReviewDecision, service: SmsSvc,
                           current_user: CurrentUser, request: Request, _: IsSuperAdmin):
    return SenderIdRead.model_validate(
        await service.reject_sender_id(sender_id, payload.reason,
                                       reviewer_id=current_user.id, ip=_client_ip(request)))


# ===================================================================== #
# Sender IDs — company admin
# ===================================================================== #
@router.get("/sender-ids", response_model=dict)
async def list_sender_ids(
    service: SmsSvc, _: CanRead,
    search: str | None = None,
    sender_status: SenderStatus | None = Query(default=None, alias="status"),
    approval_status: SenderApprovalStatus | None = None,
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
):
    rows, total = await service.list_sender_ids(
        search=search, status=sender_status, approval_status=approval_status,
        offset=(page - 1) * size, limit=size)
    return _page(rows, total, page, size, SenderIdRead)


@router.post("/sender-ids", response_model=SenderIdRead, status_code=status.HTTP_201_CREATED)
async def create_sender_id(payload: SenderIdCreate, service: SmsSvc,
                           current_user: CurrentUser, request: Request, _: CanManage):
    return SenderIdRead.model_validate(
        await service.create_sender_id(payload, actor_id=current_user.id, ip=_client_ip(request)))


@router.get("/sender-ids/{sender_id}", response_model=SenderIdRead)
async def get_sender_id(sender_id: uuid.UUID, service: SmsSvc, _: CanRead):
    return SenderIdRead.model_validate(await service.get_sender_id(sender_id))


@router.patch("/sender-ids/{sender_id}", response_model=SenderIdRead)
async def update_sender_id(sender_id: uuid.UUID, payload: SenderIdUpdate, service: SmsSvc,
                           current_user: CurrentUser, request: Request, _: CanManage):
    return SenderIdRead.model_validate(
        await service.update_sender_id(sender_id, payload, actor_id=current_user.id, ip=_client_ip(request)))


@router.post("/sender-ids/{sender_id}/set-default", response_model=SenderIdRead)
async def set_default_sender_id(sender_id: uuid.UUID, service: SmsSvc,
                                current_user: CurrentUser, request: Request, _: CanManage):
    return SenderIdRead.model_validate(
        await service.set_default_sender_id(sender_id, actor_id=current_user.id, ip=_client_ip(request)))


@router.post("/sender-ids/{sender_id}/activate", response_model=SenderIdRead)
async def activate_sender_id(sender_id: uuid.UUID, service: SmsSvc,
                             current_user: CurrentUser, request: Request, _: CanManage):
    return SenderIdRead.model_validate(
        await service.activate_sender_id(sender_id, actor_id=current_user.id, ip=_client_ip(request)))


@router.post("/sender-ids/{sender_id}/deactivate", response_model=SenderIdRead)
async def deactivate_sender_id(sender_id: uuid.UUID, service: SmsSvc,
                               current_user: CurrentUser, request: Request, _: CanManage):
    return SenderIdRead.model_validate(
        await service.deactivate_sender_id(sender_id, actor_id=current_user.id, ip=_client_ip(request)))


# ===================================================================== #
# Templates — company admin
# ===================================================================== #
@router.get("/templates", response_model=dict)
async def list_templates(
    service: SmsSvc, _: CanRead,
    search: str | None = None,
    template_status: SmsTemplateStatus | None = Query(default=None, alias="status"),
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
):
    rows, total = await service.list_templates(
        search=search, status=template_status, offset=(page - 1) * size, limit=size)
    return _page(rows, total, page, size, TemplateRead)


@router.post("/templates", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(payload: TemplateCreate, service: SmsSvc,
                          current_user: CurrentUser, request: Request, _: CanManage):
    return TemplateRead.model_validate(
        await service.create_template(payload, actor_id=current_user.id, ip=_client_ip(request)))


@router.post("/templates/preview", response_model=TemplatePreviewResponse)
async def preview_template(payload: TemplatePreviewRequest, service: SmsSvc, _: CanRead):
    return TemplatePreviewResponse(**service.preview_template(payload))


@router.get("/templates/{template_id}", response_model=TemplateRead)
async def get_template(template_id: uuid.UUID, service: SmsSvc, _: CanRead):
    return TemplateRead.model_validate(await service.get_template(template_id))


@router.patch("/templates/{template_id}", response_model=TemplateRead)
async def update_template(template_id: uuid.UUID, payload: TemplateUpdate, service: SmsSvc,
                          current_user: CurrentUser, request: Request, _: CanManage):
    return TemplateRead.model_validate(
        await service.update_template(template_id, payload, actor_id=current_user.id, ip=_client_ip(request)))


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(template_id: uuid.UUID, service: SmsSvc,
                          current_user: CurrentUser, request: Request, _: CanManage):
    await service.delete_template(template_id, actor_id=current_user.id, ip=_client_ip(request))


@router.post("/templates/{template_id}/duplicate", response_model=TemplateRead,
             status_code=status.HTTP_201_CREATED)
async def duplicate_template(template_id: uuid.UUID, service: SmsSvc,
                             current_user: CurrentUser, request: Request, _: CanManage):
    return TemplateRead.model_validate(
        await service.duplicate_template(template_id, actor_id=current_user.id, ip=_client_ip(request)))
