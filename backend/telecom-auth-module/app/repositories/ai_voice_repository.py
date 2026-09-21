"""Repositories for the AI Voice / TTS foundation.

Thin subclasses of BaseRepository — the generic get_by_id/list/create/update/
soft_delete already do everything these need; only search() methods are
added where a route needs filtering beyond the generic **filters kwargs.
"""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import func, or_, select

from app.models.ai_voice import AiVoice, TtsPreview, VoiceTemplate
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
        voices owned by that company specifically."""
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
