"""Platform settings endpoints (super-admin only).

Gated by the existing super-admin role check (require_role) — no new RBAC
permission, per the platform-settings decision. Get + update the singleton.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.api.v1.deps import (
    CurrentUser,
    get_platform_settings_service,
    require_role,
)
from app.core.constants import RoleName
from app.schemas.platform_settings import (
    PlatformSettingsRead,
    PlatformSettingsUpdate,
)
from app.services.platform_settings_service import PlatformSettingsService

router = APIRouter(prefix="/platform-settings", tags=["Platform Settings"])

SettingsDep = Annotated[
    PlatformSettingsService, Depends(get_platform_settings_service)
]
SuperAdmin = Annotated[object, Depends(require_role(RoleName.SUPER_ADMIN.value))]


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("", response_model=PlatformSettingsRead)
async def get_settings(service: SettingsDep, _: SuperAdmin) -> PlatformSettingsRead:
    return PlatformSettingsRead.model_validate(await service.get_settings())


@router.patch("", response_model=PlatformSettingsRead)
async def update_settings(
    payload: PlatformSettingsUpdate, service: SettingsDep,
    current_user: CurrentUser, request: Request, _: SuperAdmin,
) -> PlatformSettingsRead:
    row = await service.update_settings(
        payload, actor_id=current_user.id, ip=_client_ip(request)
    )
    return PlatformSettingsRead.model_validate(row)
