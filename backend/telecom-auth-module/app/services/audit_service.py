"""Audit logging service.

Writes append-only entries to audit_logs. Does NOT commit — it stages the row
on the shared session so it commits atomically with the action being audited
(same unit of work). Callers pass the actor/company/IP context.
"""
import ipaddress
import json
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


def _json_safe(value: Optional[dict]) -> Optional[dict]:
    """AuditLog.old_values/new_values are Postgres JSONB columns. Callers
    build these dicts from Pydantic's model_dump(), which by default keeps
    native Python types (UUID, datetime, Decimal, enums that aren't str
    subclasses, ...) rather than JSON-primitive ones — and the stdlib JSON
    encoder used for JSONB has no idea how to serialize a UUID, which turns
    the whole request into an unhandled 500 (found via a real "edit voice
    template, change the voice" request: `voice_id` stayed a `uuid.UUID`
    object all the way into this dict).

    Round-tripping through json.dumps(..., default=str) is a blunt but
    reliable fix: anything already JSON-safe passes through unchanged,
    anything that isn't gets stringified instead of crashing the write.
    Audit values are for a human reading a log, not for round-tripping back
    into typed objects, so stringifying is the right trade-off here.
    """
    if value is None:
        return None
    return json.loads(json.dumps(value, default=str))


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
            old_values=_json_safe(old_values),
            new_values=_json_safe(new_values),
            ip_address=_valid_inet(ip_address),
        )
        self.session.add(entry)
        # Flush (not commit) so it joins the caller's transaction.
        await self.session.flush()
        logger.info(
            "audit", extra={"action": action, "entity": entity_type}
        )