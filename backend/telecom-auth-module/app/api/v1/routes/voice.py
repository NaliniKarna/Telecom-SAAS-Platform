"""Voice Platform API routes (Phase 5).

Endpoints are organised into three groups:

  /voice/extensions/...  — Extension registry CRUD + agent-status updates.
  /voice/calls/...       — CDR reads, active-call view, originate, hangup.
  /voice/analytics/...   — Overview stats, timeseries, extension summary.

RBAC gates:
  voice.read    : GET endpoints (all authenticated company users)
  voice.manage  : POST/PATCH/DELETE on extensions; call status patch
  voice.dial    : POST /voice/calls/originate

All routes are company-scoped; super admins may not use these endpoints
(they have no company_id context) — the service enforces this.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.deps import (
    CurrentUser,
    get_voice_service,
    require_permission,
)
from app.core.constants import Permission
from app.schemas.voice import (
    AgentStatusPatch,
    CallStatusPatch,
    ExtensionStatusSummary,
    OriginateRequest,
    PaginatedCallLogs,
    VoiceCallLogRead,
    VoiceExtensionCreate,
    VoiceExtensionRead,
    VoiceExtensionUpdate,
    VoiceOverviewStats,
    VoiceTimeseriesStats,
)
from app.services.voice_service import VoiceService

router = APIRouter(prefix="/voice", tags=["Voice"])

VoiceSvc = Annotated[VoiceService, Depends(get_voice_service)]
CanRead = Annotated[object, Depends(require_permission(Permission.VOICE_READ.value))]
CanManage = Annotated[object, Depends(require_permission(Permission.VOICE_MANAGE.value))]
CanDial = Annotated[object, Depends(require_permission(Permission.VOICE_DIAL.value))]


def _ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


# ── Extensions ────────────────────────────────────────────────────────────────

@router.get("/extensions", response_model=list[VoiceExtensionRead])
async def list_extensions(
    service: VoiceSvc,
    _: CanRead,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[VoiceExtensionRead]:
    """List all extensions for the caller's company."""
    items, _ = await service.list_extensions(offset=offset, limit=limit)
    return items


@router.post(
    "/extensions",
    response_model=VoiceExtensionRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_extension(
    payload: VoiceExtensionCreate,
    service: VoiceSvc,
    current_user: CurrentUser,
    request: Request,
    _: CanManage,
) -> VoiceExtensionRead:
    """Register a new extension for the company."""
    return await service.create_extension(
        payload, actor_id=current_user.id, ip=_ip(request)
    )


@router.get("/extensions/{ext_id}", response_model=VoiceExtensionRead)
async def get_extension(
    ext_id: uuid.UUID,
    service: VoiceSvc,
    _: CanRead,
) -> VoiceExtensionRead:
    return await service.get_extension(ext_id)


@router.patch("/extensions/{ext_id}", response_model=VoiceExtensionRead)
async def update_extension(
    ext_id: uuid.UUID,
    payload: VoiceExtensionUpdate,
    service: VoiceSvc,
    current_user: CurrentUser,
    request: Request,
    _: CanManage,
) -> VoiceExtensionRead:
    return await service.update_extension(
        ext_id, payload, actor_id=current_user.id, ip=_ip(request)
    )


@router.delete("/extensions/{ext_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_extension(
    ext_id: uuid.UUID,
    service: VoiceSvc,
    current_user: CurrentUser,
    request: Request,
    _: CanManage,
) -> None:
    await service.delete_extension(
        ext_id, actor_id=current_user.id, ip=_ip(request)
    )


@router.patch(
    "/extensions/{ext_id}/agent-status",
    response_model=VoiceExtensionRead,
)
async def update_agent_status(
    ext_id: uuid.UUID,
    payload: AgentStatusPatch,
    service: VoiceSvc,
    current_user: CurrentUser,
    request: Request,
    _: CanRead,  # any user with voice.read can update their own extension's presence
) -> VoiceExtensionRead:
    """Update real-time agent presence for an extension."""
    return await service.update_agent_status(
        ext_id, payload, actor_id=current_user.id, ip=_ip(request)
    )


# ── Calls ─────────────────────────────────────────────────────────────────────

@router.get("/calls/active", response_model=list[VoiceCallLogRead])
async def list_active_calls(
    service: VoiceSvc,
    _: CanRead,
) -> list[VoiceCallLogRead]:
    """All calls currently in progress (initiated / ringing / answered)."""
    return await service.get_active_calls()


@router.get("/calls", response_model=PaginatedCallLogs)
async def list_calls(
    service: VoiceSvc,
    _: CanRead,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    direction: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    extension_id: Optional[uuid.UUID] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=80),
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
) -> PaginatedCallLogs:
    """Paginated CDR history with optional filters."""
    return await service.list_calls(
        offset=offset,
        limit=limit,
        direction=direction,
        status=status,
        extension_id=extension_id,
        search=search,
        from_date=from_date,
        to_date=to_date,
    )


@router.post(
    "/calls/originate",
    response_model=VoiceCallLogRead,
    status_code=status.HTTP_201_CREATED,
)
async def originate_call(
    payload: OriginateRequest,
    service: VoiceSvc,
    current_user: CurrentUser,
    request: Request,
    _: CanDial,
) -> VoiceCallLogRead:
    """Initiate an outbound call (click-to-call or manual dialer).

    Resolves the active PBX connection for the company and delegates to the
    AsteriskProvider (NullAsteriskProvider in simulation mode, AmiAsteriskProvider
    when TELEPHONY_PROVIDER=ami).  Always creates a CDR row regardless of the
    provider outcome.
    """
    return await service.originate_call(
        payload, actor_id=current_user.id, ip=_ip(request)
    )


@router.get("/calls/{call_id}", response_model=VoiceCallLogRead)
async def get_call(
    call_id: uuid.UUID,
    service: VoiceSvc,
    _: CanRead,
) -> VoiceCallLogRead:
    return await service.get_call(call_id)


@router.patch("/calls/{call_id}/status", response_model=VoiceCallLogRead)
async def update_call_status(
    call_id: uuid.UUID,
    payload: CallStatusPatch,
    service: VoiceSvc,
    current_user: CurrentUser,
    request: Request,
    _: CanManage,
) -> VoiceCallLogRead:
    """Advance a call's lifecycle status.

    In production this is driven by AMI events.  In simulation mode
    (NullAsteriskProvider) this endpoint lets the UI manually advance status
    through the lifecycle: initiated → answered → completed.
    """
    return await service.update_call_status(
        call_id, payload, actor_id=current_user.id, ip=_ip(request)
    )


@router.post("/calls/{call_id}/hangup", response_model=VoiceCallLogRead)
async def hangup_call(
    call_id: uuid.UUID,
    service: VoiceSvc,
    current_user: CurrentUser,
    request: Request,
    _: CanManage,
) -> VoiceCallLogRead:
    """End an active call (simulation hangup or administrative termination)."""
    return await service.hangup_call(
        call_id, actor_id=current_user.id, ip=_ip(request)
    )


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.get("/analytics/overview", response_model=VoiceOverviewStats)
async def analytics_overview(
    service: VoiceSvc,
    _: CanRead,
) -> VoiceOverviewStats:
    """High-level voice statistics: call counts, answer rate, avg duration."""
    return await service.get_overview_stats()


@router.get("/analytics/timeseries", response_model=VoiceTimeseriesStats)
async def analytics_timeseries(
    service: VoiceSvc,
    _: CanRead,
    days: int = Query(default=30, ge=7, le=365),
) -> VoiceTimeseriesStats:
    """Daily call volume for the specified period (default 30 days)."""
    return await service.get_timeseries(days=days)


@router.get("/analytics/extension-status", response_model=ExtensionStatusSummary)
async def extension_status_summary(
    service: VoiceSvc,
    _: CanRead,
) -> ExtensionStatusSummary:
    """Count of extensions by agent status (available / busy / away / offline)."""
    return await service.get_extension_status_summary()
