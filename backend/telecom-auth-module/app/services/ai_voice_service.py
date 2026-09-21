"""AI Voice / TTS foundation services.

Three responsibilities, mirroring the SMS Foundation's shape (SmsService
combines sender-IDs + templates the same way this combines voices +
templates):

  AiVoiceService      — voice library reads + activate/deactivate. No
                        creation endpoint this phase (voices are seeded/
                        managed at the platform level — see spec section 5,
                        "do NOT implement voice cloning/training yet").

  VoiceTemplateService — tenant-scoped Voice Template CRUD, template
                        rendering (reuses the SMS renderer — see below), and
                        TTS preview generation. Preview generation is
                        explicitly NOT a campaign: no recipients, no Kafka,
                        no PBX call. It calls TTSService synchronously and
                        records one TtsPreview row.

Template rendering reuse: extract_variables/render_template/missing_variables
in app.services.sms_renderer are already fully generic (only
unsupported_variables() is SMS-specific, and this module doesn't use it) —
so Voice Templates import and use those functions directly rather than
duplicating the regex engine. This is also exactly what the spec asks for
under "Template Rendering": a reusable renderer, usable later by Voice
Campaign processing — reusing the same functions IS that reusability.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import VoiceStatus, VoiceTemplateStatus
from app.core.exceptions import CompanyInactiveError, NotFoundError, ValidationError
from app.models.ai_voice import AiVoice, TtsPreview, VoiceTemplate
from app.repositories.ai_voice_repository import (
    AiVoiceRepository,
    TtsPreviewRepository,
    VoiceTemplateRepository,
)
from app.repositories.company_repository import CompanyRepository
from app.services.audit_service import AuditService
from app.services.sms_renderer import (
    extract_variables,
    missing_variables,
    render_template,
)
from app.services.tts_service import TTSService

logger = logging.getLogger(__name__)

_VOICE_ENTITY = "ai_voice"
_TEMPLATE_ENTITY = "voice_template"
_PREVIEW_ENTITY = "tts_preview"


class AiVoiceService:
    """Voice library reads + status toggling. Tenant-aware only insofar as
    list/get filter to voices visible to the caller's company (global +
    company-owned, once company-owned voices exist)."""

    def __init__(self, session: AsyncSession, ctx=None, audit: AuditService | None = None):
        self.session = session
        self.ctx = ctx
        self.audit = audit or AuditService(session)
        self.voices = AiVoiceRepository(session)

    @property
    def _company_id(self):
        return self.ctx.company_id if self.ctx else None

    async def list_voices(self, *, status=None, offset: int = 0, limit: int = 20):
        return await self.voices.list_available(
            company_id=self._company_id, status=status, offset=offset, limit=limit,
        )

    async def get_voice(self, voice_id) -> AiVoice:
        voice = await self.voices.get_available(voice_id, company_id=self._company_id)
        if voice is None:
            raise NotFoundError("Voice not found")
        return voice

    async def set_voice_status(
        self, voice_id, status: VoiceStatus, *, actor_id=None, ip=None,
    ) -> AiVoice:
        voice = await self.get_voice(voice_id)
        await self.voices.update(voice, status=status)
        await self.audit.record(
            action="activate" if status == VoiceStatus.ACTIVE else "deactivate",
            entity_type=_VOICE_ENTITY, entity_id=str(voice.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
        )
        await self.session.commit()
        await self.session.refresh(voice)
        return voice


class VoiceTemplateService:
    """Voice Template CRUD, rendering, and TTS preview generation."""

    def __init__(self, session: AsyncSession, ctx=None, audit: AuditService | None = None):
        self.session = session
        self.ctx = ctx
        self.audit = audit or AuditService(session)
        self.templates = VoiceTemplateRepository(session, ctx)
        self.voices = AiVoiceRepository(session)
        self.previews = TtsPreviewRepository(session, ctx)
        self._tts = TTSService()

    @property
    def _company_id(self):
        return self.ctx.company_id if self.ctx else None

    # --- entitlement gate --------------------------------------------------
    async def assert_ai_voice_enabled(self) -> None:
        """Company must be active AND have the AI Voice entitlement. Checked
        once, at the top of every mutating/generating action — mirrors
        ExternalSmsService.assert_company_active()."""
        company = await CompanyRepository(self.session).get_by_id(self._company_id)
        if company is None:
            raise NotFoundError("Company not found")
        if not company.is_active:
            raise CompanyInactiveError("This company's account is not active.")
        if not company.ai_voice_enabled:
            raise CompanyInactiveError(
                "AI Voice is not enabled for this company's subscription plan."
            )

    # --- CRUD ---------------------------------------------------------------
    async def list_templates(self, *, search=None, status=None, offset: int = 0, limit: int = 20):
        return await self.templates.search(search=search, status=status, offset=offset, limit=limit)

    async def get_template(self, template_id) -> VoiceTemplate:
        template = await self.templates.get_by_id(template_id)
        if template is None:
            raise NotFoundError("Voice template not found")
        return template

    async def _get_voice_or_raise(self, voice_id) -> AiVoice:
        voice = await self.voices.get_available(voice_id, company_id=self._company_id)
        if voice is None:
            raise ValidationError("Selected voice does not exist or is not available")
        return voice

    async def create_template(self, data, *, actor_id=None, ip=None) -> VoiceTemplate:
        if self._company_id is None:
            raise ValidationError("Voice templates are managed within a company")
        await self._get_voice_or_raise(data.voice_id)
        template = await self.templates.create(
            company_id=self._company_id,
            name=data.name,
            description=data.description,
            text=data.text,
            language=data.language,
            voice_id=data.voice_id,
            variables=extract_variables(data.text),
            status=data.status or VoiceTemplateStatus.ACTIVE,
        )
        await self.audit.record(
            action="create", entity_type=_TEMPLATE_ENTITY, entity_id=str(template.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            new_values={"name": template.name, "variables": template.variables},
        )
        await self.session.commit()
        await self.session.refresh(template)
        return template

    async def update_template(self, template_id, data, *, actor_id=None, ip=None) -> VoiceTemplate:
        template = await self.get_template(template_id)
        patch = data.model_dump(exclude_unset=True)
        if patch.get("voice_id"):
            await self._get_voice_or_raise(patch["voice_id"])
        if "text" in patch and patch["text"] is not None:
            patch["variables"] = extract_variables(patch["text"])
        if patch:
            await self.templates.update(template, **patch)
            await self.audit.record(
                action="update", entity_type=_TEMPLATE_ENTITY, entity_id=str(template.id),
                actor_id=actor_id, company_id=self._company_id, ip_address=ip,
                new_values=patch,
            )
            await self.session.commit()
            await self.session.refresh(template)
        return template

    async def delete_template(self, template_id, *, actor_id=None, ip=None) -> None:
        template = await self.get_template(template_id)
        await self.templates.soft_delete(template)
        await self.audit.record(
            action="delete", entity_type=_TEMPLATE_ENTITY, entity_id=str(template.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
        )
        await self.session.commit()

    # --- rendering ------------------------------------------------------------
    async def render(self, template_id, values: dict[str, str]) -> tuple[str, list[str]]:
        template = await self.get_template(template_id)
        rendered = render_template(template.text, values)
        missing = missing_variables(template.text, values)
        return rendered, missing

    # --- TTS preview ------------------------------------------------------
    async def generate_preview(
        self, template_id, values: dict[str, str], *,
        voice_id: Optional[str] = None, actor_id=None, ip=None,
    ) -> TtsPreview:
        await self.assert_ai_voice_enabled()
        template = await self.get_template(template_id)

        rendered = render_template(template.text, values)
        missing = missing_variables(template.text, values)
        if missing:
            raise ValidationError(
                f"Missing values for template variable(s): {', '.join(missing)}"
            )

        target_voice_id = voice_id or template.voice_id
        voice = await self._get_voice_or_raise(target_voice_id)
        if voice.status != VoiceStatus.ACTIVE.value:
            raise ValidationError("Selected voice is not active")

        result = self._tts.synthesize_and_store(
            text=rendered,
            provider_voice_id=voice.provider_voice_id,
            storage_prefix=f"tts/{self._company_id}",
        )

        preview = await self.previews.create(
            company_id=self._company_id,
            voice_template_id=template.id,
            voice_id=voice.id,
            rendered_text=rendered,
            audio_url=result.audio_url,
            duration_seconds=result.duration_seconds,
            char_count=result.char_count,
            created_by=actor_id,
        )
        await self.audit.record(
            action="tts_preview_generated", entity_type=_PREVIEW_ENTITY,
            entity_id=str(preview.id), actor_id=actor_id,
            company_id=self._company_id, ip_address=ip,
            new_values={"voice_template_id": str(template.id), "char_count": result.char_count},
        )
        await self.session.commit()
        await self.session.refresh(preview)
        return preview
