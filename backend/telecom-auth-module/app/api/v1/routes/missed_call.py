"""Missed Call Platform API routes (Phase 6).

Endpoints are organised into four groups:

  /missed-calls/...              — List + create missed calls
  /missed-calls/{id}/...         — Detail, status, assignment
  /missed-calls/{id}/notes/...   — Append notes
  /missed-calls/{id}/callbacks/... — Initiate callback, record outcome
  /missed-calls/dashboard        — Overview stats

RBAC:
  missed_call.read   : GET endpoints (company_admin + company_user)
  missed_call.manage : POST/PATCH (company_admin)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.deps import (
    CurrentUser,
    get_missed_call_service,
    require_permission,
)
from app.core.constants import Permission
from app.schemas.missed_call import (
    CallbackOutcomePatch,
    CallbackRequest,
    MissedCallAssignPatch,
    MissedCallCallbackRead,
    MissedCallCreate,
    MissedCallDashboardStats,
    MissedCallDetail,
    MissedCallNoteCreate,
    MissedCallNoteRead,
    MissedCallRead,
    MissedCallStatusPatch,
    PaginatedMissedCalls,
)
from app.services.missed_call_service import MissedCallService

router = APIRouter(prefix="/missed-calls", tags=["Missed Calls"])

McSvc = Annotated[MissedCallService, Depends(get_missed_call_service)]
CanRead = Annotated[
    object, Depends(require_permission(Permission.MISSED_CALL_READ.value))
]
CanManage = Annotated[
    object, Depends(require_permission(Permission.MISSED_CALL_MANAGE.value))
]


def _ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


# ── List / Create ─────────────────────────────────────────────────────────────

@router.get("", response_model=PaginatedMissedCalls)
async def list_missed_calls(
    service: McSvc,
    _: CanRead,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    assigned_to: Optional[uuid.UUID] = Query(default=None),
    search: Optional[str] = Query(default=None, max_length=80),
    from_date: Optional[datetime] = Query(default=None),
    to_date: Optional[datetime] = Query(default=None),
) -> PaginatedMissedCalls:
    """Paginated missed-call list with filters."""
    return await service.list_missed_calls(
        offset=offset,
        limit=limit,
        status=status,
        assigned_to=assigned_to,
        search=search,
        from_date=from_date,
        to_date=to_date,
    )


@router.post(
    "",
    response_model=MissedCallRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_missed_call(
    payload: MissedCallCreate,
    service: McSvc,
    current_user: CurrentUser,
    request: Request,
    _: CanManage,
) -> MissedCallRead:
    """Register a new missed call (from AMI event or manual entry)."""
    return await service.create_missed_call(
        payload, actor_id=current_user.id, ip=_ip(request)
    )


# ── Detail / Status / Assignment ──────────────────────────────────────────────

@router.get("/{mc_id}", response_model=MissedCallDetail)
async def get_missed_call(
    mc_id: uuid.UUID,
    service: McSvc,
    _: CanRead,
) -> MissedCallDetail:
    """Full detail view with notes and callback history."""
    return await service.get_missed_call(mc_id)


@router.patch("/{mc_id}/status", response_model=MissedCallRead)
async def update_status(
    mc_id: uuid.UUID,
    payload: MissedCallStatusPatch,
    service: McSvc,
    current_user: CurrentUser,
    request: Request,
    _: CanManage,
) -> MissedCallRead:
    return await service.update_status(
        mc_id, payload, actor_id=current_user.id, ip=_ip(request)
    )


@router.patch("/{mc_id}/assign", response_model=MissedCallRead)
async def assign_missed_call(
    mc_id: uuid.UUID,
    payload: MissedCallAssignPatch,
    service: McSvc,
    current_user: CurrentUser,
    request: Request,
    _: CanManage,
) -> MissedCallRead:
    """Assign (or unassign) a missed call to a company user."""
    return await service.assign(
        mc_id, payload, actor_id=current_user.id, ip=_ip(request)
    )


# ── Notes ─────────────────────────────────────────────────────────────────────

@router.post(
    "/{mc_id}/notes",
    response_model=MissedCallNoteRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_note(
    mc_id: uuid.UUID,
    payload: MissedCallNoteCreate,
    service: McSvc,
    current_user: CurrentUser,
    request: Request,
    _: CanManage,
) -> MissedCallNoteRead:
    return await service.add_note(
        mc_id, payload, actor_id=current_user.id, ip=_ip(request)
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────

@router.post(
    "/{mc_id}/callbacks",
    response_model=MissedCallCallbackRead,
    status_code=status.HTTP_201_CREATED,
)
async def initiate_callback(
    mc_id: uuid.UUID,
    payload: CallbackRequest,
    service: McSvc,
    current_user: CurrentUser,
    request: Request,
    _: CanManage,
) -> MissedCallCallbackRead:
    """Initiate a callback call via the Voice Platform and record the attempt."""
    return await service.initiate_callback(
        mc_id, payload, actor_id=current_user.id, ip=_ip(request)
    )


@router.patch(
    "/{mc_id}/callbacks/{cb_id}/outcome",
    response_model=MissedCallCallbackRead,
)
async def update_callback_outcome(
    mc_id: uuid.UUID,
    cb_id: uuid.UUID,
    payload: CallbackOutcomePatch,
    service: McSvc,
    current_user: CurrentUser,
    request: Request,
    _: CanManage,
) -> MissedCallCallbackRead:
    """Record the outcome of a callback attempt."""
    return await service.update_callback_outcome(
        mc_id, cb_id, payload, actor_id=current_user.id, ip=_ip(request)
    )


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard/stats", response_model=MissedCallDashboardStats)
async def dashboard_stats(
    service: McSvc,
    _: CanRead,
) -> MissedCallDashboardStats:
    """Overview missed-call stats for the company dashboard."""
    return await service.get_dashboard_stats()
