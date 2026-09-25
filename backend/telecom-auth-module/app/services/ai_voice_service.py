"""AI Voice / TTS foundation services.

  AiVoiceService       — Company Admin's voice-library READS. Filtered
                        through the company's current subscription plan
                        (see SubscriptionPlanVoice, added for Super Admin
                        management) — a company only ever sees voices its
                        plan actually grants. No mutation capability at
                        all: activating/deactivating a voice, or curating
                        which voices a plan grants, are platform-owned
                        actions now handled exclusively by
                        AdminAiVoiceService (see spec ownership rules,
                        "Company Admin must NOT be able to modify
                        platform-owned voice/provider configuration").

  VoiceTemplateService  — tenant-scoped Voice Template CRUD, template
                        rendering (reuses the SMS renderer — see below), and
                        TTS preview generation. Preview generation is
                        explicitly NOT a campaign: no recipients, no Kafka,
                        no PBX call. It calls TTSService synchronously and
                        records one TtsPreview row.

  AdminAiVoiceService   — Super Admin's platform-level layer: the voice
                        catalog itself (create/edit/activate/deactivate —
                        no company scoping, no plan filtering, since these
                        ARE the platform configuration a plan filters
                        against) and which voices each subscription plan
                        grants. Gated exclusively by require_role(SUPER_ADMIN)
                        at the route layer (see app.api.v1.routes.admin_ai_voice)
                        — this does not depend on, or intersect with, any
                        Company Admin permission.

Template rendering reuse: extract_variables/render_template/missing_variables
in app.services.sms_renderer are already fully generic (only
unsupported_variables() is SMS-specific, and this module doesn't use it) —
so Voice Templates import and use those functions directly rather than
duplicating the regex engine.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import VoiceStatus, VoiceTemplateStatus
from app.core.exceptions import CompanyInactiveError, NotFoundError, ValidationError
from app.models.ai_voice import AiVoice, TtsPreview, VoiceTemplate
from app.repositories.ai_voice_repository import (
    AiVoiceRepository,
    SubscriptionPlanVoiceRepository,
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
from app.services.tts_usage_service import TtsUsageService

logger = logging.getLogger(__name__)

_VOICE_ENTITY = "ai_voice"
_TEMPLATE_ENTITY = "voice_template"
_PREVIEW_ENTITY = "tts_preview"
_PLAN_ENTITY = "subscription_plan"

_UNSET = object()


async def _load_plan_id(session: AsyncSession, company_id) -> Optional[str]:
    """Shared by AiVoiceService and VoiceTemplateService — both need the
    company's current plan_id to filter voices through
    SubscriptionPlanVoice. A missing company or missing plan resolves to
    None, which the repository layer already treats as "no global voices
    visible" (safe default, not an error) rather than raising here.
    """
    if company_id is None:
        return None
    company = await CompanyRepository(session).get_by_id(company_id)
    return company.plan_id if company else None


class AiVoiceService:
    """Company Admin's voice-library reads. See module docstring — no
    mutation methods live here on purpose."""

    def __init__(self, session: AsyncSession, ctx=None, audit: AuditService | None = None):
        self.session = session
        self.ctx = ctx
        self.audit = audit or AuditService(session)
        self.voices = AiVoiceRepository(session)
        self._plan_id_cache = _UNSET

    @property
    def _company_id(self):
        return self.ctx.company_id if self.ctx else None

    async def _plan_id(self):
        if self._plan_id_cache is _UNSET:
            self._plan_id_cache = await _load_plan_id(self.session, self._company_id)
        return self._plan_id_cache

    async def list_voices(self, *, offset: int = 0, limit: int = 20):
        """Company Admin always sees active-only, regardless of caller
        input — there's no legitimate reason to browse a voice you can't
        select, and this is the "must no longer be selectable" requirement
        applied to browsing, not just to mutation paths (which
        _get_voice_or_raise on VoiceTemplateService already enforced
        correctly before this fix — this closes the matching gap on the
        list/detail views).
        """
        plan_id = await self._plan_id()
        return await self.voices.list_visible_to_company(
            company_id=self._company_id, plan_id=plan_id,
            status=VoiceStatus.ACTIVE.value, offset=offset, limit=limit,
        )

    async def get_voice(self, voice_id) -> AiVoice:
        plan_id = await self._plan_id()
        voice = await self.voices.get_visible_to_company(
            voice_id, company_id=self._company_id, plan_id=plan_id,
        )
        if voice is None or voice.status != VoiceStatus.ACTIVE.value:
            raise NotFoundError("Voice not found")
        return voice


class VoiceTemplateService:
    """Voice Template CRUD, rendering, and TTS preview generation."""

    def __init__(
        self, session: AsyncSession, ctx=None, audit: AuditService | None = None,
        tts_usage: TtsUsageService | None = None,
    ):
        self.session = session
        self.ctx = ctx
        self.audit = audit or AuditService(session)
        self.templates = VoiceTemplateRepository(session, ctx)
        self.voices = AiVoiceRepository(session)
        self.previews = TtsPreviewRepository(session, ctx)
        self._tts = TTSService()
        self.usage = tts_usage or TtsUsageService(session)
        self._plan_id_cache = _UNSET
        self._monthly_limit_cache = _UNSET

    @property
    def _company_id(self):
        return self.ctx.company_id if self.ctx else None

    async def _plan_id(self):
        if self._plan_id_cache is _UNSET:
            self._plan_id_cache = await _load_plan_id(self.session, self._company_id)
        return self._plan_id_cache

    async def _monthly_tts_limit(self):
        """The company's plan-level monthly TTS character ceiling (NULL =
        unlimited). Cached per service instance, same rationale as
        _plan_id() above — this service is constructed fresh per request."""
        if self._monthly_limit_cache is _UNSET:
            company = await CompanyRepository(self.session).get_by_id(self._company_id)
            self._monthly_limit_cache = (
                company.plan.default_monthly_tts_characters
                if company and company.plan else None
            )
        return self._monthly_limit_cache

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
        """Enforcement point for spec requirement 7 items 3+4: the voice
        must both be active AND available under the company's current
        subscription plan. A voice that fails either check is treated
        exactly like one that doesn't exist — no distinction is leaked to
        the caller about which reason applies, matching how the rest of
        this app avoids being an oracle for enumeration.
        """
        plan_id = await self._plan_id()
        voice = await self.voices.get_visible_to_company(
            voice_id, company_id=self._company_id, plan_id=plan_id,
        )
        if voice is None:
            raise ValidationError(
                "Selected voice does not exist or is not available under your company's plan"
            )
        if voice.status != VoiceStatus.ACTIVE.value:
            raise ValidationError("Selected voice is not active")
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
        """TTS usage accounting (Phase 4A quota metering): the character
        count is known before the provider is ever called, so this
        reserves that exact amount first. A successful synthesis converts
        the reservation to real consumed usage; any failure (including a
        provider error re-raised from TTSService) releases it instead —
        matching the spec's "successful preview counts as consumed, failed
        does not" rule. Each call reserves against a FRESH preview id, so a
        user re-clicking "Generate" after a failure never double-counts a
        previous attempt — it's simply a new reservation.
        """
        await self.assert_ai_voice_enabled()
        template = await self.get_template(template_id)

        rendered = render_template(template.text, values)
        missing = missing_variables(template.text, values)
        if missing:
            raise ValidationError(
                f"Missing values for template variable(s): {', '.join(missing)}"
            )

        target_voice_id = voice_id or template.voice_id
        # _get_voice_or_raise already enforces active + plan-availability —
        # no separate status check needed here.
        voice = await self._get_voice_or_raise(target_voice_id)

        char_count = len(rendered)
        preview_id = uuid.uuid4()
        monthly_limit = await self._monthly_tts_limit()

        # Raises ValidationError (422) if this would exceed the monthly
        # ceiling — nothing has been generated or stored yet at this point.
        await self.usage.reserve(
            company_id=self._company_id, monthly_limit=monthly_limit,
            characters=char_count, reference_type="tts_preview", reference_id=preview_id,
        )

        try:
            result = self._tts.synthesize_and_store(
                text=rendered,
                provider_voice_id=voice.provider_voice_id,
                storage_prefix=f"tts/{self._company_id}",
            )
        except Exception:
            await self.usage.release(reference_type="tts_preview", reference_id=preview_id)
            await self.session.commit()
            raise

        await self.usage.consume(reference_type="tts_preview", reference_id=preview_id)

        preview = await self.previews.create(
            id=preview_id,
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


class AdminAiVoiceService:
    """Super Admin's platform-level AI Voice management.

    No company/tenant scoping anywhere in this class — the voice catalog
    and plan-voice availability ARE the platform configuration everything
    else filters against, per the spec's ownership rules. Gated exclusively
    by require_role(SUPER_ADMIN) at the route layer, same pattern already
    used by app.api.v1.routes.subscription_plans — no new RBAC permission
    was needed for that gate.
    """

    def __init__(self, session: AsyncSession, audit: AuditService | None = None):
        self.session = session
        self.audit = audit or AuditService(session)
        self.voices = AiVoiceRepository(session)
        self.plan_voices = SubscriptionPlanVoiceRepository(session)
        self._tts = TTSService()

    # --- voice catalog -------------------------------------------------
    async def list_voices(self, *, search=None, status=None, offset: int = 0, limit: int = 20):
        return await self.voices.search_all(search=search, status=status, offset=offset, limit=limit)

    async def get_voice(self, voice_id) -> AiVoice:
        voice = await self.voices.get_by_id(voice_id)
        if voice is None:
            raise NotFoundError("Voice not found")
        return voice

    async def create_voice(self, data, *, actor_id=None, ip=None) -> AiVoice:
        voice = await self.voices.create(
            company_id=None,  # platform voice — company-owned custom voices are a future capability
            name=data.name,
            language=data.language,
            gender=data.gender,
            description=data.description,
            provider=data.provider,
            provider_voice_id=data.provider_voice_id,
            status=data.status or VoiceStatus.ACTIVE,
        )
        await self.audit.record(
            action="create", entity_type=_VOICE_ENTITY, entity_id=str(voice.id),
            actor_id=actor_id, ip_address=ip,
            new_values={
                "name": voice.name, "provider": voice.provider,
                "provider_voice_id": voice.provider_voice_id,
            },
        )
        await self.session.commit()
        await self.session.refresh(voice)
        return voice

    async def update_voice(self, voice_id, data, *, actor_id=None, ip=None) -> AiVoice:
        voice = await self.get_voice(voice_id)
        patch = data.model_dump(exclude_unset=True)
        if patch:
            await self.voices.update(voice, **patch)
            await self.audit.record(
                action="update", entity_type=_VOICE_ENTITY, entity_id=str(voice.id),
                actor_id=actor_id, ip_address=ip, new_values=patch,
            )
            await self.session.commit()
            await self.session.refresh(voice)
        return voice

    async def set_voice_status(
        self, voice_id, status: VoiceStatus, *, actor_id=None, ip=None,
    ) -> AiVoice:
        """A deactivated voice becomes immediately unselectable by every
        Company Admin — enforced by AiVoiceRepository's status filter and
        VoiceTemplateService._get_voice_or_raise, both of which live
        upstream of any cache, so this takes effect on the very next
        company-side request.
        """
        voice = await self.get_voice(voice_id)
        await self.voices.update(voice, status=status)
        await self.audit.record(
            action="activate" if status == VoiceStatus.ACTIVE else "deactivate",
            entity_type=_VOICE_ENTITY, entity_id=str(voice.id),
            actor_id=actor_id, ip_address=ip,
        )
        await self.session.commit()
        await self.session.refresh(voice)
        return voice

    # --- plan <-> voice availability ------------------------------------
    async def list_plan_voice_ids(self, plan_id) -> list:
        return await self.plan_voices.list_voice_ids_for_plan(plan_id)

    async def set_plan_voices(
        self, plan_id, voice_ids: list, *, actor_id=None, ip=None,
    ) -> list:
        added, removed = await self.plan_voices.set_voices_for_plan(plan_id, voice_ids)
        if added or removed:
            await self.audit.record(
                action="plan_voices_updated", entity_type=_PLAN_ENTITY,
                entity_id=str(plan_id), actor_id=actor_id, ip_address=ip,
                new_values={
                    "added": [str(v) for v in added],
                    "removed": [str(v) for v in removed],
                },
            )
        await self.session.commit()
        return await self.plan_voices.list_voice_ids_for_plan(plan_id)

    # --- ad-hoc TTS preview ---------------------------------------------
    async def generate_preview(self, text: str, voice_id, *, actor_id=None, ip=None):
        """No template, no company, no persisted TtsPreview row — that
        table is scoped to a company + Voice Template (company_id and
        voice_template_id are both NOT NULL), which doesn't fit a
        platform-level smoke test of a voice. Reuses the exact same
        TTSService every other TTS path in the app uses; nothing here
        talks to a provider directly.
        """
        voice = await self.get_voice(voice_id)
        if voice.status != VoiceStatus.ACTIVE.value:
            raise ValidationError("Selected voice is not active")

        result = self._tts.synthesize_and_store(
            text=text, provider_voice_id=voice.provider_voice_id,
            storage_prefix="tts/admin-preview",
        )
        await self.audit.record(
            action="admin_tts_preview_generated", entity_type=_VOICE_ENTITY,
            entity_id=str(voice.id), actor_id=actor_id, ip_address=ip,
            new_values={"char_count": result.char_count},
        )
        await self.session.commit()
        return result, voice
