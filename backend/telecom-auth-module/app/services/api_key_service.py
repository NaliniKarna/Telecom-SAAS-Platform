"""API key service — company-scoped, tenant-isolated via the repo's ctx.

Generate returns the plaintext key exactly once; only the SHA-256 hash and a
display prefix are persisted. Revoke is a soft flag. Status (active/revoked/
expired) is derived at read time. Generate and revoke are audited.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ApiKeyStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import generate_api_key
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
            usage_count=0,
        )
        await self.audit.record(
            action="create", entity_type=_ENTITY, entity_id=str(key.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            new_values={"name": key.name, "key_prefix": key.key_prefix,
                        "expires_at": _s(key.expires_at)},
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


def _s(v) -> Any:
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)
