"""Audit log read service.

Read-only query use cases for the platform audit trail. Maps joined rows to
enriched DTOs (actor email/name, company name) so the UI doesn't deal in raw
UUIDs. Writes are handled separately by AuditService.
"""
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit_log_repository import AuditLogRepository
from app.schemas.audit_log import AuditFacets, AuditLogFilter, AuditLogRead


class AuditLogService:
    def __init__(self, session: AsyncSession, repo: AuditLogRepository):
        self.session = session
        self.audit = repo

    async def list_logs(
        self, *, offset: int, limit: int, filters: AuditLogFilter | None = None
    ) -> tuple[Sequence[AuditLogRead], int]:
        f = filters or AuditLogFilter()
        rows, total = await self.audit.search(
            offset=offset, limit=limit, search=f.search,
            company_id=f.company_id, actor_id=f.actor_id,
            action=f.action, entity_type=f.entity_type,
            date_from=f.date_from, date_to=f.date_to, sort_dir=f.sort_dir,
        )
        items: list[AuditLogRead] = []
        for log, actor_email, actor_first, actor_last, company_name in rows:
            item = AuditLogRead.model_validate(log)
            item.actor_email = actor_email
            full = " ".join(filter(None, [actor_first, actor_last]))
            item.actor_name = full or actor_email
            item.company_name = company_name
            # INET renders as an object; coerce to str for the API.
            item.ip_address = str(log.ip_address) if log.ip_address else None
            items.append(item)
        return items, total

    async def facets(self) -> AuditFacets:
        return AuditFacets(
            actions=await self.audit.distinct_actions(),
            modules=await self.audit.distinct_modules(),
        )
