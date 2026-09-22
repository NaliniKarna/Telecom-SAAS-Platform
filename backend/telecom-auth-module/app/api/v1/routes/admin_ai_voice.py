"""Super Admin AI Voice / TTS platform management.

Gated exclusively by the existing super-admin role check (require_role) —
no new RBAC permission is introduced, same pattern as
app.api.v1.routes.subscription_plans. This access does not depend on, or
intersect with, any Company Admin permission (ai_voice.read/manage/preview
are irrelevant here).

Platform-owned resources managed here (spec section 15): the voice catalog
itself, and which voices each subscription plan grants. Company-owned
resources (Voice Templates, generated previews) are NOT reachable from this
router — those stay under /ai-voice, Company Admin's own namespace.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.deps import CurrentUser, get_admin_ai_voice_service, require_role
from app.core.constants import RoleName, VoiceStatus
from app.core.http import client_ip
from app.schemas.ai_voice import (
    AdminTtsPreviewRequest,
    AdminTtsPreviewResponse,
    PlanVoicesRead,
    PlanVoicesSet,
    VoiceCreate,
    VoiceRead,
    VoiceUpdate,
)
from app.services.ai_voice_service import AdminAiVoiceService

router = APIRouter(prefix="/admin/ai-voice", tags=["Admin: AI Voice"])

AdminVoiceSvc = Annotated[AdminAiVoiceService, Depends(get_admin_ai_voice_service)]
SuperAdmin = Annotated[object, Depends(require_role(RoleName.SUPER_ADMIN.value))]


def _page(rows, total, page, size, schema):
    return {
        "data": [schema.model_validate(r).model_dump(mode="json") for r in rows],
        "meta": {"page": page, "size": size, "total": total,
                 "pages": (total + size - 1) // size if size else 0},
    }


# =========================================================================== #
# Voice catalog (platform-owned)
# =========================================================================== #
@router.get("/voices", response_model=dict)
async def list_voices(
    service: AdminVoiceSvc, _: SuperAdmin,
    search: str | None = None,
    status_filter: VoiceStatus | None = Query(None, alias="status"),
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
):
    rows, total = await service.list_voices(
        search=search, status=status_filter, offset=(page - 1) * size, limit=size,
    )
    return _page(rows, total, page, size, VoiceRead)


@router.get("/voices/{voice_id}", response_model=VoiceRead)
async def get_voice(voice_id: uuid.UUID, service: AdminVoiceSvc, _: SuperAdmin):
    return VoiceRead.model_validate(await service.get_voice(voice_id))


@router.post("/voices", response_model=VoiceRead, status_code=status.HTTP_201_CREATED)
async def create_voice(
    payload: VoiceCreate, service: AdminVoiceSvc, current_user: CurrentUser,
    request: Request, _: SuperAdmin,
):
    voice = await service.create_voice(
        payload, actor_id=current_user.id, ip=client_ip(request),
    )
    return VoiceRead.model_validate(voice)


@router.patch("/voices/{voice_id}", response_model=VoiceRead)
async def update_voice(
    voice_id: uuid.UUID, payload: VoiceUpdate, service: AdminVoiceSvc,
    current_user: CurrentUser, request: Request, _: SuperAdmin,
):
    voice = await service.update_voice(
        voice_id, payload, actor_id=current_user.id, ip=client_ip(request),
    )
    return VoiceRead.model_validate(voice)


@router.post("/voices/{voice_id}/activate", response_model=VoiceRead)
async def activate_voice(
    voice_id: uuid.UUID, service: AdminVoiceSvc, current_user: CurrentUser,
    request: Request, _: SuperAdmin,
):
    voice = await service.set_voice_status(
        voice_id, VoiceStatus.ACTIVE, actor_id=current_user.id, ip=client_ip(request),
    )
    return VoiceRead.model_validate(voice)


@router.post("/voices/{voice_id}/deactivate", response_model=VoiceRead)
async def deactivate_voice(
    voice_id: uuid.UUID, service: AdminVoiceSvc, current_user: CurrentUser,
    request: Request, _: SuperAdmin,
):
    voice = await service.set_voice_status(
        voice_id, VoiceStatus.INACTIVE, actor_id=current_user.id, ip=client_ip(request),
    )
    return VoiceRead.model_validate(voice)


# =========================================================================== #
# Plan <-> voice availability
# =========================================================================== #
@router.get("/plans/{plan_id}/voices", response_model=PlanVoicesRead)
async def get_plan_voices(plan_id: uuid.UUID, service: AdminVoiceSvc, _: SuperAdmin):
    voice_ids = await service.list_plan_voice_ids(plan_id)
    return PlanVoicesRead(voice_ids=voice_ids)


@router.put("/plans/{plan_id}/voices", response_model=PlanVoicesRead)
async def set_plan_voices(
    plan_id: uuid.UUID, payload: PlanVoicesSet, service: AdminVoiceSvc,
    current_user: CurrentUser, request: Request, _: SuperAdmin,
):
    voice_ids = await service.set_plan_voices(
        plan_id, payload.voice_ids, actor_id=current_user.id, ip=client_ip(request),
    )
    return PlanVoicesRead(voice_ids=voice_ids)


# =========================================================================== #
# Ad-hoc TTS preview (no template, no company, no campaign — see
# AdminAiVoiceService.generate_preview)
# =========================================================================== #
@router.post("/tts/preview", response_model=AdminTtsPreviewResponse)
async def generate_admin_tts_preview(
    payload: AdminTtsPreviewRequest, service: AdminVoiceSvc,
    current_user: CurrentUser, request: Request, _: SuperAdmin,
):
    result, voice = await service.generate_preview(
        payload.text, payload.voice_id,
        actor_id=current_user.id, ip=client_ip(request),
    )
    return AdminTtsPreviewResponse(
        voice_id=voice.id, text=payload.text, audio_url=result.audio_url,
        duration_seconds=result.duration_seconds, char_count=result.char_count,
    )
