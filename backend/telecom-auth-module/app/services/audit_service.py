"""Audit logging service.

Writes append-only entries to audit_logs. Does NOT commit — it stages the row
on the shared session so it commits atomically with the action being audited
(same unit of work). Callers pass the actor/company/IP context.
"""
import ipaddress
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def _valid_inet(value: Optional[str]) -> Optional[str]:
    """AuditLog.ip_address is a Postgres INET column — asyncpg rejects any
    string that isn't a real IPv4/IPv6 address at the driver level, which
    turns the whole request into an unhandled 500 (this is how it was found:
    Starlette's TestClient reports its host as the literal string
    "testclient", not an IP). Every caller ultimately traces back to
    app.core.http.client_ip(), which is normally a real IP, but this is the
    single choke point that makes the audit trail itself unable to crash a
    request over a malformed/unexpected value here.
    """
    if not value:
        return None
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        logger.warning("audit_ip_invalid", extra={"value": value})
        return None


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
            ip_address=_valid_inet(ip_address),
        )
        self.session.add(entry)
        # Flush (not commit) so it joins the caller's transaction.
        await self.session.flush()
        logger.info(
            "audit", extra={"action": action, "entity": entity_type}
        )