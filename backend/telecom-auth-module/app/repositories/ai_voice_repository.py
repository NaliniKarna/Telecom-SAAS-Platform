"""Repositories for the AI Voice / TTS foundation.

Thin subclasses of BaseRepository — the generic get_by_id/list/create/update/
soft_delete already do everything these need; only search() methods are
added where a route needs filtering beyond the generic **filters kwargs.
"""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import and_, delete, func, or_, select

from app.models.ai_voice import AiVoice, SubscriptionPlanVoice, TtsPreview, VoiceTemplate
from app.repositories.base import BaseRepository


class AiVoiceRepository(BaseRepository[AiVoice]):
    model = AiVoice
    # Voices are platform-wide by default (company_id NULL) with room for
    # future per-company custom voices. The base class's tenant filter would
    # hide every NULL-company_id (global) voice from a tenant-scoped ctx, so
    # scoping is handled explicitly here instead of via tenant_scoped=True.
    tenant_scoped = False

    async def list_available(
        self, *, company_id, status=None, offset: int = 0, limit: int = 20,
    ) -> tuple[Sequence[AiVoice], int]:
        """Voices visible to a company: global (company_id IS NULL) plus any
        voices owned by that company specifically.

        Superseded for Company Admin-facing reads by list_visible_to_company()
        (plan-aware) — kept for any caller that genuinely wants the
        unrestricted global set (e.g. Super Admin's own tooling reusing this
        instead of the dedicated search()/list() below).
        """
        stmt = select(AiVoice).where(AiVoice.deleted_at.is_(None)).where(
            or_(AiVoice.company_id.is_(None), AiVoice.company_id == company_id)
        )
        if status is not None:
            stmt = stmt.where(AiVoice.status == status)

        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = stmt.order_by(AiVoice.created_at.asc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    async def get_available(self, voice_id, *, company_id) -> AiVoice | None:
        stmt = select(AiVoice).where(
            AiVoice.id == voice_id,
            AiVoice.deleted_at.is_(None),
            or_(AiVoice.company_id.is_(None), AiVoice.company_id == company_id),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    def _plan_visibility_clause(self, *, company_id, plan_id):
        """Global voices assigned to `plan_id` via subscription_plan_voices,
        union company-owned voices (future custom-voice capability). If
        plan_id is None (company has no plan), the subquery's `= NULL`
        never matches — no global voices are visible, which is the correct
        safe-by-default behavior, not a bug.
        """
        plan_voice_ids = select(SubscriptionPlanVoice.voice_id).where(
            SubscriptionPlanVoice.plan_id == plan_id
        )
        return or_(
            AiVoice.company_id == company_id,
            and_(AiVoice.company_id.is_(None), AiVoice.id.in_(plan_voice_ids)),
        )

    async def list_visible_to_company(
        self, *, company_id, plan_id, status=None, offset: int = 0, limit: int = 20,
    ) -> tuple[Sequence[AiVoice], int]:
        """Voices a Company Admin may actually select: global voices their
        subscription plan grants, plus any voice the company itself owns.
        This is the enforcement point for spec requirement 7.4 ("requested
        voice is available under the company's plan") on the LIST path.
        """
        stmt = select(AiVoice).where(AiVoice.deleted_at.is_(None)).where(
            self._plan_visibility_clause(company_id=company_id, plan_id=plan_id)
        )
        if status is not None:
            stmt = stmt.where(AiVoice.status == status)

        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = stmt.order_by(AiVoice.created_at.asc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    async def get_visible_to_company(self, voice_id, *, company_id, plan_id) -> AiVoice | None:
        """Single-voice counterpart of list_visible_to_company() — the
        enforcement point for spec requirement 7.4 on every other path
        (template create/update, TTS preview, future campaign voice
        selection): a voice that exists but isn't on the company's plan is
        treated exactly like a voice that doesn't exist.
        """
        stmt = select(AiVoice).where(
            AiVoice.id == voice_id,
            AiVoice.deleted_at.is_(None),
            self._plan_visibility_clause(company_id=company_id, plan_id=plan_id),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def search_all(
        self, *, search: str | None = None, status=None,
        offset: int = 0, limit: int = 20,
    ) -> tuple[Sequence[AiVoice], int]:
        """Super Admin's unrestricted view: every voice, any status,
        regardless of plan — there is no "availability" concept for the
        platform administrator managing the catalog itself.
        """
        stmt = select(AiVoice).where(AiVoice.deleted_at.is_(None))
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(AiVoice.name.ilike(like), AiVoice.description.ilike(like)))
        if status is not None:
            stmt = stmt.where(AiVoice.status == status)

        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = stmt.order_by(AiVoice.created_at.desc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total


class SubscriptionPlanVoiceRepository:
    """Not a BaseRepository subclass — this association table has no
    single-row identity or tenant scoping to inherit; it's managed as a
    whole set per plan (list current / replace-all), which is exactly what
    the Super Admin "Allowed AI Voices" UI needs.
    """

    def __init__(self, session):
        self.session = session

    async def list_voice_ids_for_plan(self, plan_id) -> list:
        stmt = select(SubscriptionPlanVoice.voice_id).where(
            SubscriptionPlanVoice.plan_id == plan_id
        )
        return [row[0] for row in (await self.session.execute(stmt)).all()]

    async def set_voices_for_plan(self, plan_id, voice_ids: list) -> tuple[set, set]:
        """Replace the plan's full voice set. Returns (added, removed) ids
        so the caller can write one clear audit entry per change instead of
        one per row.
        """
        current = set(await self.list_voice_ids_for_plan(plan_id))
        target = set(voice_ids)
        added, removed = target - current, current - target

        if removed:
            await self.session.execute(
                delete(SubscriptionPlanVoice).where(
                    SubscriptionPlanVoice.plan_id == plan_id,
                    SubscriptionPlanVoice.voice_id.in_(removed),
                )
            )
        for voice_id in added:
            self.session.add(SubscriptionPlanVoice(plan_id=plan_id, voice_id=voice_id))

        await self.session.flush()
        return added, removed


class VoiceTemplateRepository(BaseRepository[VoiceTemplate]):
    model = VoiceTemplate
    tenant_scoped = True

    async def search(
        self, *, search: str | None = None, status=None,
        offset: int = 0, limit: int = 20,
    ) -> tuple[Sequence[VoiceTemplate], int]:
        stmt = self._base_select()
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(
                VoiceTemplate.name.ilike(like), VoiceTemplate.text.ilike(like),
            ))
        if status is not None:
            stmt = stmt.where(VoiceTemplate.status == status)

        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = stmt.order_by(VoiceTemplate.created_at.desc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total


class TtsPreviewRepository(BaseRepository[TtsPreview]):
    model = TtsPreview
    tenant_scoped = True

    async def list_for_template(
        self, voice_template_id, *, offset: int = 0, limit: int = 20,
    ) -> tuple[Sequence[TtsPreview], int]:
        stmt = self._base_select().where(TtsPreview.voice_template_id == voice_template_id)
        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = stmt.order_by(TtsPreview.created_at.desc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

