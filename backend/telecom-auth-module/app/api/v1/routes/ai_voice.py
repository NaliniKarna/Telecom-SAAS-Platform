"""AI Voice / TTS foundation endpoints — Company Admin's view.

RBAC:
  - reads (voices, templates)     -> ai_voice.read
  - writes (templates)            -> ai_voice.manage
  - TTS preview generation        -> ai_voice.preview

Voice library here is READ-ONLY. Activating/deactivating a voice and
curating which voices a subscription plan grants are platform-owned
actions, moved to app.api.v1.routes.admin_ai_voice (Super Admin only, per
the ownership rules: "Company Admin must NOT be able to modify
platform-owned voice/provider configuration"). The voice list below is
already filtered to what the company's plan actually grants — see
AiVoiceService / AiVoiceRepository.list_visible_to_company().

Explicitly NOT part of this module (see spec section 15): Voice Campaigns,
campaign recipients, Kafka publishing, bulk generation, or any PBX call
origination. Preview generation never creates a campaign, never touches
Kafka, never originates a call.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.v1.deps import (
    CurrentUser,
    get_ai_voice_service,
    get_voice_template_service,
    require_permission,
)
from app.core.constants import Permission
from app.core.http import client_ip
from app.schemas.ai_voice import (
    TtsPreviewRequest,
    TtsPreviewResponse,
    VoiceRead,
    VoiceTemplateCreate,
    VoiceTemplateRead,
    VoiceTemplateRenderRequest,
    VoiceTemplateRenderResponse,
    VoiceTemplateUpdate,
)
from app.services.ai_voice_service import AiVoiceService, VoiceTemplateService

router = APIRouter(prefix="/ai-voice", tags=["AI Voice"])

VoiceSvc = Annotated[AiVoiceService, Depends(get_ai_voice_service)]
TemplateSvc = Annotated[VoiceTemplateService, Depends(get_voice_template_service)]
CanRead = Annotated[object, Depends(require_permission(Permission.AI_VOICE_READ.value))]
CanManage = Annotated[object, Depends(require_permission(Permission.AI_VOICE_MANAGE.value))]
CanPreview = Annotated[object, Depends(require_permission(Permission.AI_VOICE_PREVIEW.value))]


def _page(rows, total, page, size, schema):
    return {
        "data": [schema.model_validate(r).model_dump(mode="json") for r in rows],
        "meta": {"page": page, "size": size, "total": total,
                 "pages": (total + size - 1) // size if size else 0},
    }


# =========================================================================== #
# Voice library (read-only — see module docstring)
# =========================================================================== #
@router.get("/voices", response_model=dict)
async def list_voices(
    service: VoiceSvc, _: CanRead,
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
):
    # No status filter exposed here — Company Admin's view is always
    # active-only (see AiVoiceService.list_voices docstring). Browsing
    # inactive/unavailable platform voices is a Super Admin concern
    # (GET /admin/ai-voice/voices).
    rows, total = await service.list_voices(offset=(page - 1) * size, limit=size)
    return _page(rows, total, page, size, VoiceRead)


@router.get("/voices/{voice_id}", response_model=VoiceRead)
async def get_voice(voice_id: uuid.UUID, service: VoiceSvc, _: CanRead):
    return VoiceRead.model_validate(await service.get_voice(voice_id))


# =========================================================================== #
# Voice Templates
# =========================================================================== #
@router.get("/templates", response_model=dict)
async def list_templates(
    service: TemplateSvc, _: CanRead,
    search: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
):
    rows, total = await service.list_templates(
        search=search, status=status_filter, offset=(page - 1) * size, limit=size,
    )
    return _page(rows, total, page, size, VoiceTemplateRead)


@router.post("/templates", response_model=VoiceTemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: VoiceTemplateCreate, service: TemplateSvc, current_user: CurrentUser,
    request: Request, _: CanManage,
):
    template = await service.create_template(
        payload, actor_id=current_user.id, ip=client_ip(request),
    )
    return VoiceTemplateRead.model_validate(template)


@router.get("/templates/{template_id}", response_model=VoiceTemplateRead)
async def get_template(template_id: uuid.UUID, service: TemplateSvc, _: CanRead):
    return VoiceTemplateRead.model_validate(await service.get_template(template_id))


@router.patch("/templates/{template_id}", response_model=VoiceTemplateRead)
async def update_template(
    template_id: uuid.UUID, payload: VoiceTemplateUpdate, service: TemplateSvc,
    current_user: CurrentUser, request: Request, _: CanManage,
):
    template = await service.update_template(
        template_id, payload, actor_id=current_user.id, ip=client_ip(request),
    )
    return VoiceTemplateRead.model_validate(template)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID, service: TemplateSvc, current_user: CurrentUser,
    request: Request, _: CanManage,
):
    await service.delete_template(template_id, actor_id=current_user.id, ip=client_ip(request))


# =========================================================================== #
# Rendering + TTS preview
# =========================================================================== #
@router.post("/templates/{template_id}/render", response_model=VoiceTemplateRenderResponse)
async def render_template(
    template_id: uuid.UUID, payload: VoiceTemplateRenderRequest,
    service: TemplateSvc, _: CanRead,
):
    rendered, missing = await service.render(template_id, payload.values)
    return VoiceTemplateRenderResponse(rendered_text=rendered, missing_variables=missing)


@router.post(
    "/templates/{template_id}/tts-preview",
    response_model=TtsPreviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_tts_preview(
    template_id: uuid.UUID, payload: TtsPreviewRequest, service: TemplateSvc,
    current_user: CurrentUser, request: Request, _: CanPreview,
):
    preview = await service.generate_preview(
        template_id, payload.values, voice_id=payload.voice_id,
        actor_id=current_user.id, ip=client_ip(request),
    )
    return TtsPreviewResponse.model_validate(preview)
