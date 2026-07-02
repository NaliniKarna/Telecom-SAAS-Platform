"""Generic, tenant-scoped base repository.

The base is the single choke-point for tenant isolation: every scoped query
is automatically filtered by company_id derived from the request context.
Repositories return models or None; they never raise NotFound (a business
decision left to services) and never commit (transactions belong to services).
"""
from typing import Any, Generic, Optional, Sequence, Type, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import TenantContext
from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    model: Type[ModelType]
    #: whether this model carries a company_id column to scope by
    tenant_scoped: bool = True

    def __init__(
        self, session: AsyncSession, tenant_ctx: Optional[TenantContext] = None
    ):
        self.session = session
        self.ctx = tenant_ctx

    # ----- scoping ----------------------------------------------------------
    def _apply_tenant_scope(self, stmt: Select) -> Select:
        if not self.tenant_scoped:
            return stmt
        if self.ctx is None or self.ctx.is_super_admin:
            return stmt  # platform-level access; no narrowing
        return stmt.where(self.model.company_id == self.ctx.company_id)

    def _apply_soft_delete(self, stmt: Select) -> Select:
        if hasattr(self.model, "deleted_at"):
            return stmt.where(self.model.deleted_at.is_(None))
        return stmt

    def _base_select(self) -> Select:
        return self._apply_soft_delete(self._apply_tenant_scope(select(self.model)))

    # ----- reads ------------------------------------------------------------
    async def get_by_id(self, entity_id: Any) -> Optional[ModelType]:
        stmt = self._base_select().where(self.model.id == entity_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list(
        self, *, offset: int = 0, limit: int = 20, **filters: Any
    ) -> tuple[Sequence[ModelType], int]:
        stmt = self._base_select()
        for field, value in filters.items():
            if value is not None and hasattr(self.model, field):
                stmt = stmt.where(getattr(self.model, field) == value)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = stmt.offset(offset).limit(limit).order_by(self.model.created_at.desc())
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    # ----- writes (no commit; service owns the transaction) -----------------
    async def create(self, **data: Any) -> ModelType:
        obj = self.model(**data)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, obj: ModelType, **data: Any) -> ModelType:
        for field, value in data.items():
            setattr(obj, field, value)
        await self.session.flush()
        return obj

    async def soft_delete(self, obj: ModelType) -> None:
        from datetime import datetime, timezone

        if hasattr(obj, "deleted_at"):
            obj.deleted_at = datetime.now(timezone.utc)
            await self.session.flush()
        else:
            await self.session.delete(obj)
            await self.session.flush()
