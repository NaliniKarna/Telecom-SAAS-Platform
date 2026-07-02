"""Contact list endpoints (Company Admin). Tenant-scoped via TenantContext.

Reads gated by contact.read; writes by contact.manage.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.deps import CurrentUser, get_contact_list_service, require_permission
from app.core.constants import Permission
from app.models.contact import Contact, ContactListMember
from app.schemas.contact import (
    AddContactsRequest,
    ContactListCreate,
    ContactListListItem,
    ContactListMemberRead,
    ContactListRead,
    ContactListUpdate,
)
from app.services.contact_list_service import ContactListService

router = APIRouter(prefix="/contact-lists", tags=["Contact Lists"])

ListSvc = Annotated[ContactListService, Depends(get_contact_list_service)]
CanRead = Annotated[object, Depends(require_permission(Permission.CONTACT_READ.value))]
CanManage = Annotated[object, Depends(require_permission(Permission.CONTACT_MANAGE.value))]


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _list_item(lst, count: int) -> ContactListListItem:
    item = ContactListListItem.model_validate(lst)
    item.member_count = count
    return item


def _read(lst, count: int) -> ContactListRead:
    r = ContactListRead.model_validate(lst)
    r.member_count = count
    return r


def _member(m: ContactListMember, c: Contact) -> ContactListMemberRead:
    return ContactListMemberRead(
        id=m.id, contact_id=c.id, first_name=c.first_name, last_name=c.last_name,
        mobile_e164=c.mobile_e164, email=c.email, added_at=m.created_at,
    )


@router.get("", response_model=dict)
async def list_contact_lists(
    service: ListSvc, _: CanRead,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> dict:
    rows, total = await service.list_lists(search=search, offset=(page - 1) * size, limit=size)
    return {
        "data": [_list_item(l, c).model_dump(mode="json") for l, c in rows],
        "meta": {"page": page, "size": size, "total": total,
                 "pages": (total + size - 1) // size},
    }


@router.post("", response_model=ContactListRead, status_code=status.HTTP_201_CREATED)
async def create_contact_list(
    payload: ContactListCreate, service: ListSvc, current_user: CurrentUser,
    request: Request, _: CanManage,
) -> ContactListRead:
    lst = await service.create_list(payload, actor_id=current_user.id, ip=_client_ip(request))
    return _read(lst, 0)


@router.get("/{list_id}", response_model=ContactListRead)
async def get_contact_list(
    list_id: uuid.UUID, service: ListSvc, _: CanRead,
) -> ContactListRead:
    lst, count = await service.get_list(list_id)
    return _read(lst, count)


@router.patch("/{list_id}", response_model=ContactListRead)
async def update_contact_list(
    list_id: uuid.UUID, payload: ContactListUpdate, service: ListSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
) -> ContactListRead:
    lst, count = await service.update_list(list_id, payload, actor_id=current_user.id, ip=_client_ip(request))
    return _read(lst, count)


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact_list(
    list_id: uuid.UUID, service: ListSvc, current_user: CurrentUser,
    request: Request, _: CanManage,
) -> None:
    await service.delete_list(list_id, actor_id=current_user.id, ip=_client_ip(request))


@router.get("/{list_id}/members", response_model=list[ContactListMemberRead])
async def list_members(
    list_id: uuid.UUID, service: ListSvc, _: CanRead,
) -> list[ContactListMemberRead]:
    rows = await service.list_members(list_id)
    return [_member(m, c) for m, c in rows]


@router.post("/{list_id}/members", response_model=list[ContactListMemberRead])
async def add_contacts(
    list_id: uuid.UUID, payload: AddContactsRequest, service: ListSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
) -> list[ContactListMemberRead]:
    rows = await service.add_contacts(list_id, payload.contact_ids, actor_id=current_user.id, ip=_client_ip(request))
    return [_member(m, c) for m, c in rows]


@router.delete("/{list_id}/members/{contact_id}", response_model=list[ContactListMemberRead])
async def remove_contact(
    list_id: uuid.UUID, contact_id: uuid.UUID, service: ListSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
) -> list[ContactListMemberRead]:
    rows = await service.remove_contact(list_id, contact_id, actor_id=current_user.id, ip=_client_ip(request))
    return [_member(m, c) for m, c in rows]
