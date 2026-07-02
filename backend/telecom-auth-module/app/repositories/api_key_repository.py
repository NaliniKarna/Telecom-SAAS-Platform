"""API key repository — tenant-scoped via BaseRepository (company_id from ctx)."""
from typing import Optional, Sequence

from sqlalchemy import func, select

from app.models.api_key import ApiKey
from app.repositories.base import BaseRepository


class ApiKeyRepository(BaseRepository[ApiKey]):
    model = ApiKey
    tenant_scoped = True

    async def list_for_company(
        self, *, offset: int = 0, limit: int = 20
    ) -> tuple[Sequence[ApiKey], int]:
        stmt = self._base_select()
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        stmt = stmt.order_by(ApiKey.created_at.desc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    async def get_by_hash(self, key_hash: str) -> Optional[ApiKey]:
        """Auth-time lookup (not tenant-scoped: the key itself identifies the
        tenant). Used by future request-authentication; included for completeness."""
        return (await self.session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash)
        )).scalars().first()
