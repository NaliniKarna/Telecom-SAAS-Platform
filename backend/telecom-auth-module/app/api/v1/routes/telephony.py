"""Telephony connection endpoints (FreePBX / Asterisk integration layer).

Hybrid topology:
  - Company admins manage their own company's connection(s) (company_id set).
  - Super admins manage the shared platform-default (company_id NULL) by passing
    is_platform_default=true on create. The service enforces that only a super
    admin can create/own the platform default.

Reads are gated by telephony.read, writes by telephony.manage. The AMI secret is
write-only: accepted on create/update, encrypted at rest, and never serialized
back (reads expose secret_set: bool only).

Connection tests and effective-status run through the AsteriskProvider seam
(NullAsteriskProvider by default), so every endpoint works without a live PBX;
flipping TELEPHONY_PROVIDER=ami switches to the real AMI adapter with no change
here.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.v1.deps import CurrentUser, get_telephony_service, require_role
from app.core.constants import RoleName
from app.schemas.telephony import (
    ConnectionTestResult,
    EffectiveStatus,
    TelephonyConnectionCreate,
    TelephonyConnectionRead,
    TelephonyConnectionUpdate,
)
from app.services.telephony_service import TelephonyService

router = APIRouter(prefix="/telephony", tags=["Telephony"])

TelephonySvc = Annotated[TelephonyService, Depends(get_telephony_service)]
# Provider-managed: PBX infrastructure is super-admin only. Gating by role
# (not just permission) makes the boundary explicit and robust.
IsSuperAdmin = Annotated[object, Depends(require_role(RoleName.SUPER_ADMIN.value))]


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


# --------------------------------------------------------------------------- #
# Connections CRUD
# --------------------------------------------------------------------------- #
@router.get("/connections", response_model=list[TelephonyConnectionRead])
async def list_connections(service: TelephonySvc, _: IsSuperAdmin) -> list[TelephonyConnectionRead]:
    rows = await service.list_connections()
    return [TelephonyConnectionRead.from_model(r) for r in rows]


@router.post(
    "/connections",
    response_model=TelephonyConnectionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_connection(
    payload: TelephonyConnectionCreate, service: TelephonySvc,
    current_user: CurrentUser, request: Request, _: IsSuperAdmin,
) -> TelephonyConnectionRead:
    row = await service.create_connection(
        payload, actor_id=current_user.id, ip=_client_ip(request)
    )
    return TelephonyConnectionRead.from_model(row)


@router.get("/connections/{conn_id}", response_model=TelephonyConnectionRead)
async def get_connection(
    conn_id: uuid.UUID, service: TelephonySvc, _: IsSuperAdmin,
) -> TelephonyConnectionRead:
    row = await service.get_connection(conn_id)
    return TelephonyConnectionRead.from_model(row)


@router.patch("/connections/{conn_id}", response_model=TelephonyConnectionRead)
async def update_connection(
    conn_id: uuid.UUID, payload: TelephonyConnectionUpdate, service: TelephonySvc,
    current_user: CurrentUser, request: Request, _: IsSuperAdmin,
) -> TelephonyConnectionRead:
    row = await service.update_connection(
        conn_id, payload, actor_id=current_user.id, ip=_client_ip(request)
    )
    return TelephonyConnectionRead.from_model(row)


@router.delete("/connections/{conn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(
    conn_id: uuid.UUID, service: TelephonySvc, current_user: CurrentUser,
    request: Request, _: IsSuperAdmin,
) -> None:
    await service.delete_connection(
        conn_id, actor_id=current_user.id, ip=_client_ip(request)
    )


# --------------------------------------------------------------------------- #
# Live status
# --------------------------------------------------------------------------- #
@router.post("/connections/{conn_id}/test", response_model=ConnectionTestResult)
async def test_connection(
    conn_id: uuid.UUID, service: TelephonySvc, current_user: CurrentUser,
    request: Request, _: IsSuperAdmin,
) -> ConnectionTestResult:
    """Probe a specific connection and persist its last_status. Runs through the
    active provider (Null by default), so it works without a live PBX."""
    return await service.test_connection(
        conn_id, actor_id=current_user.id, ip=_client_ip(request)
    )


@router.get("/status", response_model=EffectiveStatus)
async def effective_status(service: TelephonySvc, _: IsSuperAdmin) -> EffectiveStatus:
    """The connection that would actually be used for the caller's company after
    hybrid resolution (own override, else platform default), plus a live probe.
    Read-only: does not persist last_status."""
    source, conn, status_result = await service.effective_status()
    return EffectiveStatus(
        source=source,
        connection=TelephonyConnectionRead.from_model(conn) if conn else None,
        status=status_result,
    )
