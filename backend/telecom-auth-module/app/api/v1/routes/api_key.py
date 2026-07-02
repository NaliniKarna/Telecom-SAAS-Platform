"""API Key endpoints (Company Admin). Tenant-scoped via TenantContext.

Per-action RBAC: list -> apikey.read, generate -> apikey.generate,
revoke -> apikey.revoke. The plaintext key is returned only by the generate
endpoint, exactly once.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.deps import (
    CurrentUser,
    get_api_key_service,
    require_permission,
)
from app.core.constants import Permission
from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyCreated, ApiKeyRead
from app.services.api_key_service import ApiKeyService, derive_status

router = APIRouter(prefix="/api-keys", tags=["API Keys"])

ApiKeySvc = Annotated[ApiKeyService, Depends(get_api_key_service)]
CanRead = Annotated[object, Depends(require_permission(Permission.APIKEY_READ.value))]
CanGenerate = Annotated[
    object, Depends(require_permission(Permission.APIKEY_GENERATE.value))
]
CanRevoke = Annotated[
    object, Depends(require_permission(Permission.APIKEY_REVOKE.value))
]


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


def _read(key: ApiKey) -> ApiKeyRead:
    r = ApiKeyRead.model_validate(key)
    r.status = derive_status(key).value
    return r


@router.get("", response_model=dict)
async def list_api_keys(
    service: ApiKeySvc, _: CanRead,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> dict:
    rows, total = await service.list_keys(offset=(page - 1) * size, limit=size)
    return {
        "data": [_read(k).model_dump(mode="json") for k in rows],
        "meta": {"page": page, "size": size, "total": total,
                 "pages": (total + size - 1) // size},
    }


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def generate_api_key(
    payload: ApiKeyCreate, service: ApiKeySvc, current_user: CurrentUser,
    request: Request, _: CanGenerate,
) -> ApiKeyCreated:
    key, full_key = await service.generate(
        payload, actor_id=current_user.id, ip=_client_ip(request)
    )
    base = _read(key)
    # The ONLY place the plaintext key is ever returned.
    return ApiKeyCreated(**base.model_dump(), api_key=full_key)


@router.post("/{key_id}/revoke", response_model=ApiKeyRead)
async def revoke_api_key(
    key_id: uuid.UUID, service: ApiKeySvc, current_user: CurrentUser,
    request: Request, _: CanRevoke,
) -> ApiKeyRead:
    key = await service.revoke(
        key_id, actor_id=current_user.id, ip=_client_ip(request)
    )
    return _read(key)
