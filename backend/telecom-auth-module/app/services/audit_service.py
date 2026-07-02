"""Audit logging service.

Writes append-only entries to audit_logs. Does NOT commit — it stages the row
on the shared session so it commits atomically with the action being audited
(same unit of work). Callers pass the actor/company/IP context.
"""
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        actor_id: Optional[Any] = None,
        company_id: Optional[Any] = None,
        description: Optional[str] = None,
        old_values: Optional[dict] = None,
        new_values: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        entry = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            actor_id=actor_id,
            company_id=company_id,
            description=description,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
        )
        self.session.add(entry)
        # Flush (not commit) so it joins the caller's transaction.
        await self.session.flush()
        logger.info(
            "audit", extra={"action": action, "entity": entity_type}
        )
