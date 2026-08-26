"""API key service — company-scoped, tenant-isolated via the repo's ctx.

Generate returns the plaintext key exactly once; only the SHA-256 hash and a
display prefix are persisted. Revoke is a soft flag. Status (active/revoked/
expired) is derived at read time. Generate and revoke are audited.

`authenticate_api_key()` is the request-authentication path itself (used by
app.api.v1.deps.get_api_key_context): it is the one place is_ip_allowed() is
actually enforced.
"""
import ipaddress
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ApiKeyStatus
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.security import generate_api_key, hash_api_key
from app.models.api_key import ApiKey
from app.repositories.api_key_repository import ApiKeyRepository
from app.schemas.api_key import ApiKeyCreate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_ENTITY = "api_key"


def derive_status(key: ApiKey) -> ApiKeyStatus:
    if key.revoked_at is not None:
        return ApiKeyStatus.REVOKED
    if key.expires_at is not None and key.expires_at <= datetime.now(timezone.utc):
        return ApiKeyStatus.EXPIRED
    return ApiKeyStatus.ACTIVE


def is_ip_allowed(key: ApiKey, client_ip: Optional[str]) -> bool:
    """True if client_ip is permitted by the key's whitelist.

    An empty/null whitelist allows any IP (backward compatible with keys
    created before this field existed). This is the enforcement point for
    the future request-authentication scheme; it is not yet wired into any
    live auth path since none exists today.
    """
    if not key.ip_whitelist:
        return True
    if not client_ip:
        return False
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for entry in key.ip_whitelist:
        try:
            if addr in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


class ApiKeyService:
    def __init__(
        self,
        session: AsyncSession,
        repo: ApiKeyRepository,
        audit: AuditService | None = None,
    ):
        self.session = session
        self.repo = repo
        self.audit = audit or AuditService(session)

    @property
    def _company_id(self):
        return self.repo.ctx.company_id if self.repo.ctx else None

    async def list_keys(self, *, offset: int, limit: int):
        return await self.repo.list_for_company(offset=offset, limit=limit)

    async def generate(
        self, data: ApiKeyCreate, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> tuple[ApiKey, str]:
        if self._company_id is None:
            raise ValidationError("API keys are managed within a company")
        if data.expires_at is not None and data.expires_at <= datetime.now(timezone.utc):
            raise ValidationError("Expiry must be in the future")

        full_key, prefix, key_hash = generate_api_key()
        key = await self.repo.create(
            company_id=self._company_id,
            name=data.name,
            description=data.description,
            key_prefix=prefix,
            key_hash=key_hash,
            created_by=actor_id,
            expires_at=data.expires_at,
            ip_whitelist=data.ip_whitelist,
            usage_count=0,
        )
        await self.audit.record(
            action="create", entity_type=_ENTITY, entity_id=str(key.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            new_values={"name": key.name, "key_prefix": key.key_prefix,
                        "expires_at": _s(key.expires_at),
                        "ip_whitelist": key.ip_whitelist},
        )
        await self.session.commit()
        await self.session.refresh(key)
        # full_key is returned to the caller ONCE and never stored.
        return key, full_key

    async def revoke(
        self, key_id, *, actor_id: Optional[Any] = None, ip: Optional[str] = None,
    ) -> ApiKey:
        key = await self.repo.get_by_id(key_id)  # tenant + scoped
        if key is None:
            raise NotFoundError("API key not found")
        if key.revoked_at is not None:
            raise ConflictError("This API key is already revoked")
        key.revoked_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.audit.record(
            action="revoke", entity_type=_ENTITY, entity_id=str(key.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            old_values={"name": key.name, "key_prefix": key.key_prefix},
        )
        await self.session.commit()
        await self.session.refresh(key)
        return key


@dataclass
class ApiKeyContext:
    """Authenticated principal for a programmatic (API-key) request.

    Deliberately distinct from TenantContext: there is no human user behind
    an API key, so there's no user_id/roles to carry. company_id is still
    the source of truth downstream repositories should scope by — treat it
    the same way TenantContext.company_id is treated (never trust client
    input over this)."""

    key_id: Any
    company_id: Any
    key_name: str


async def authenticate_api_key(
    session: AsyncSession,
    presented_key: str,
    *,
    client_ip: Optional[str] = None,
    audit: Optional[AuditService] = None,
) -> ApiKeyContext:
    """Validate a presented `X-API-Key` value end-to-end.

    Order of checks: key exists -> not revoked/expired -> caller IP is in
    the key's whitelist (is_ip_allowed). Unknown/inactive keys are rejected
    with the same generic message so a caller can't distinguish "wrong key"
    from "your key was revoked" by probing. On success, updates
    last_used_at/usage_count and returns the resolved company context.

    Raises:
        AuthenticationError: key not found, revoked, or expired.
        PermissionDeniedError: key is valid but client_ip isn't whitelisted.
    """
    repo = ApiKeyRepository(session, tenant_ctx=None)
    audit = audit or AuditService(session)

    key = await repo.get_by_hash(hash_api_key(presented_key))
    if key is None or derive_status(key) != ApiKeyStatus.ACTIVE:
        raise AuthenticationError("Invalid or inactive API key")

    if not is_ip_allowed(key, client_ip):
        await audit.record(
            action="auth_denied_ip",
            entity_type=_ENTITY,
            entity_id=str(key.id),
            company_id=key.company_id,
            ip_address=client_ip,
            description=f"Request IP not in whitelist for key '{key.name}'",
        )
        await session.commit()
        raise PermissionDeniedError("Request IP is not permitted for this API key")

    key.last_used_at = datetime.now(timezone.utc)
    key.usage_count = (key.usage_count or 0) + 1
    await session.flush()
    await session.commit()

    return ApiKeyContext(key_id=key.id, company_id=key.company_id, key_name=key.name)


async def audit_ip_lockout(session: AsyncSession, client_ip: str) -> None:
    """Records that an IP was locked out after repeated invalid-key attempts.

    Called from the auth dependency (app.api.v1.deps.get_api_key_context),
    not from authenticate_api_key itself, since the lockout decision lives
    in the in-process rate limiter the dependency owns.
    """
    audit = AuditService(session)
    await audit.record(
        action="auth_ip_locked",
        entity_type=_ENTITY,
        ip_address=client_ip,
        description="IP temporarily blocked after repeated invalid API key attempts",
    )
    await session.commit()


async def audit_key_rate_limited(
    session: AsyncSession, key_ctx: "ApiKeyContext", client_ip: Optional[str],
) -> None:
    """Records that a valid, authenticated key exceeded its request rate limit."""
    audit = AuditService(session)
    await audit.record(
        action="auth_key_rate_limited",
        entity_type=_ENTITY,
        entity_id=str(key_ctx.key_id),
        company_id=key_ctx.company_id,
        ip_address=client_ip,
        description=f"Request rate limit exceeded for key '{key_ctx.key_name}'",
    )
    await session.commit()


def _s(v) -> Any:
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)