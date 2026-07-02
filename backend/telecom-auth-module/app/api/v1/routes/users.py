"""Company user management endpoints (Company Admin scope).

Gated by the existing user.* permissions (already granted to company_admin).
All write ops pass the acting user's id + company_id from the authenticated
context — never from the client — and the service enforces role restriction,
self-protection, and tenant isolation.

The accept-invite endpoint is intentionally public (pre-auth): the invitee has
no account session yet, only the invite token.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status

from app.api.v1.deps import (
    CurrentUser,
    get_auth_service,  # noqa: F401  (kept for symmetry / future use)
    get_public_user_management_service,
    get_user_management_service,
    require_permission,
)
from app.core.constants import Permission, UserStatus
from app.schemas.common import PageMeta, PageParams
from app.schemas.user import (
    AcceptInvite,
    UserFilter,
    UserInvite,
    UserListItem,
    UserRead,
    UserUpdate,
)
from app.services.email_service import EmailService
from app.services.user_management_service import UserManagementService

router = APIRouter(prefix="/users", tags=["User Management"])

UserSvc = Annotated[UserManagementService, Depends(get_user_management_service)]


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _to_read(user) -> UserRead:
    r = UserRead.model_validate(user)
    r.roles = user.role_names
    return r


@router.get("", response_model=dict)
async def list_users(
    service: UserSvc,
    _: Annotated[object, Depends(require_permission(Permission.USER_READ.value))],
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    status_filter: UserStatus | None = Query(None, alias="status"),
    role: str | None = Query(None),
    sort_by: str = Query("created_at"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
) -> dict:
    params = PageParams(page=page, size=size)
    filters = UserFilter(
        search=search, status=status_filter, role=role,
        sort_by=sort_by, sort_dir=sort_dir,
    )
    rows, total = await service.list_users(
        offset=params.offset, limit=params.size, filters=filters
    )
    items = []
    for u in rows:
        item = UserListItem.model_validate(u)
        item.roles = u.role_names
        items.append(item)
    pages = (total + params.size - 1) // params.size
    return {
        "data": items,
        "meta": PageMeta(
            page=params.page, size=params.size, total=total, pages=pages
        ).model_dump(),
        "errors": [],
    }


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def invite_user(
    payload: UserInvite, service: UserSvc, current_user: CurrentUser,
    request: Request, background: BackgroundTasks,
    _: Annotated[object, Depends(require_permission(Permission.USER_CREATE.value))],
) -> UserRead:
    user, token = await service.invite_user(
        payload, company_id=current_user.company_id,
        actor_id=current_user.id, ip=_client_ip(request),
    )
    # Send the invite out-of-band (dev mode logs the link).
    background.add_task(EmailService().send_invite, user.email, token)
    return _to_read(user)


@router.post("/accept-invite", response_model=UserRead)
async def accept_invite(
    payload: AcceptInvite,
    service: Annotated[
        UserManagementService, Depends(get_public_user_management_service)
    ],
) -> UserRead:
    # Public: the invitee authenticates with the invite token, not a session.
    # Uses the context-free service so no access token is required.
    user = await service.accept_invite(payload)
    return _to_read(user)


@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: uuid.UUID, service: UserSvc,
    _: Annotated[object, Depends(require_permission(Permission.USER_READ.value))],
) -> UserRead:
    return _to_read(await service.get_user(user_id))


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID, payload: UserUpdate, service: UserSvc,
    current_user: CurrentUser, request: Request,
    _: Annotated[object, Depends(require_permission(Permission.USER_UPDATE.value))],
) -> UserRead:
    user = await service.update_user(
        user_id, payload, company_id=current_user.company_id,
        actor_id=current_user.id, ip=_client_ip(request),
    )
    return _to_read(user)


@router.post("/{user_id}/activate", response_model=UserRead)
async def activate_user(
    user_id: uuid.UUID, service: UserSvc, current_user: CurrentUser,
    request: Request,
    _: Annotated[object, Depends(require_permission(Permission.USER_ACTIVATE.value))],
) -> UserRead:
    user = await service.set_active(
        user_id, True, company_id=current_user.company_id,
        actor_id=current_user.id, ip=_client_ip(request),
    )
    return _to_read(user)


@router.post("/{user_id}/deactivate", response_model=UserRead)
async def deactivate_user(
    user_id: uuid.UUID, service: UserSvc, current_user: CurrentUser,
    request: Request,
    _: Annotated[
        object, Depends(require_permission(Permission.USER_DEACTIVATE.value))
    ],
) -> UserRead:
    user = await service.set_active(
        user_id, False, company_id=current_user.company_id,
        actor_id=current_user.id, ip=_client_ip(request),
    )
    return _to_read(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID, service: UserSvc, current_user: CurrentUser,
    request: Request,
    _: Annotated[object, Depends(require_permission(Permission.USER_DELETE.value))],
) -> None:
    await service.delete_user(
        user_id, company_id=current_user.company_id,
        actor_id=current_user.id, ip=_client_ip(request),
    )