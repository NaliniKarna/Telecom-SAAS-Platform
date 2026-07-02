"""Group endpoints (Company Admin; group.manage). Tenant-scoped via the repo's
TenantContext — a caller only ever sees/touches groups in their own company.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import desc, select

from app.api.v1.deps import CurrentUser, DbSession, get_group_service, require_permission
from app.core.constants import GroupStatus, GroupType, Permission
from app.models.audit_log import AuditLog
from app.schemas.group import (
    AddMembersRequest,
    GroupCreate,
    GroupFilter,
    GroupListItem,
    GroupMemberRead,
    GroupRead,
    GroupUpdate,
)
from app.services.group_service import GroupService

router = APIRouter(prefix="/groups", tags=["Groups"])

GroupSvc = Annotated[GroupService, Depends(get_group_service)]
CanManage = Annotated[
    object, Depends(require_permission(Permission.GROUP_MANAGE.value))
]


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _list_item(group, count: int) -> GroupListItem:
    item = GroupListItem.model_validate(group)
    item.member_count = count
    return item


def _read(group, count: int) -> GroupRead:
    r = GroupRead.model_validate(group)
    r.member_count = count
    return r


def _member(m, u) -> GroupMemberRead:
    return GroupMemberRead(
        id=m.id, user_id=u.id, email=u.email,
        full_name=" ".join(filter(None, [u.first_name, u.last_name])) or None,
        status=u.status.value if hasattr(u.status, "value") else str(u.status),
        added_at=m.created_at,
    )


@router.get("", response_model=dict)
async def list_groups(
    service: GroupSvc, _: CanManage,
    search: str | None = None,
    group_status: GroupStatus | None = Query(default=None, alias="status"),
    group_type: GroupType | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> dict:
    flt = GroupFilter(search=search, status=group_status, group_type=group_type)
    rows, total = await service.list_groups(flt, offset=(page - 1) * size, limit=size)
    return {
        "data": [_list_item(g, c).model_dump(mode="json") for g, c in rows],
        "meta": {"page": page, "size": size, "total": total,
                 "pages": (total + size - 1) // size},
    }


@router.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate, service: GroupSvc, current_user: CurrentUser,
    request: Request, _: CanManage,
) -> GroupRead:
    group = await service.create_group(
        payload, actor_id=current_user.id, ip=_client_ip(request)
    )
    return _read(group, 0)


@router.get("/{group_id}", response_model=GroupRead)
async def get_group(
    group_id: uuid.UUID, service: GroupSvc, _: CanManage,
) -> GroupRead:
    group, count = await service.get_group(group_id)
    return _read(group, count)


@router.patch("/{group_id}", response_model=GroupRead)
async def update_group(
    group_id: uuid.UUID, payload: GroupUpdate, service: GroupSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
) -> GroupRead:
    group, count = await service.update_group(
        group_id, payload, actor_id=current_user.id, ip=_client_ip(request)
    )
    return _read(group, count)


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: uuid.UUID, service: GroupSvc, current_user: CurrentUser,
    request: Request, _: CanManage,
) -> None:
    await service.delete_group(
        group_id, actor_id=current_user.id, ip=_client_ip(request)
    )


@router.get("/{group_id}/members", response_model=list[GroupMemberRead])
async def list_members(
    group_id: uuid.UUID, service: GroupSvc, _: CanManage,
) -> list[GroupMemberRead]:
    rows = await service.list_members(group_id)
    return [_member(m, u) for m, u in rows]


@router.post("/{group_id}/members", response_model=list[GroupMemberRead])
async def add_members(
    group_id: uuid.UUID, payload: AddMembersRequest, service: GroupSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
) -> list[GroupMemberRead]:
    rows = await service.add_members(
        group_id, payload.user_ids, actor_id=current_user.id,
        ip=_client_ip(request),
    )
    return [_member(m, u) for m, u in rows]


@router.delete("/{group_id}/members/{user_id}", response_model=list[GroupMemberRead])
async def remove_member(
    group_id: uuid.UUID, user_id: uuid.UUID, service: GroupSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
) -> list[GroupMemberRead]:
    rows = await service.remove_member(
        group_id, user_id, actor_id=current_user.id, ip=_client_ip(request)
    )
    return [_member(m, u) for m, u in rows]


@router.get("/{group_id}/activity", response_model=list[dict])
async def group_activity(
    group_id: uuid.UUID, service: GroupSvc, db: DbSession, _: CanManage,
    limit: int = Query(default=20, ge=1, le=50),
) -> list[dict]:
    # Tenant guard: ensures the group exists within the caller's company.
    await service.get_group(group_id)
    rows = (await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_type == "group", AuditLog.entity_id == str(group_id))
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )).scalars().all()
    return [
        {
            "id": str(log.id),
            "action": log.action,
            "actor_id": str(log.actor_id) if log.actor_id else None,
            "old_values": log.old_values,
            "new_values": log.new_values,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in rows
    ]
