"""User data access."""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.constants import RoleName, UserStatus
from app.models.role import Role
from app.models.user import User, UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User
    tenant_scoped = True

    async def get_by_email(self, email: str) -> Optional[User]:
        """Lookup by email across the platform (login). Not tenant-scoped:
        login happens before a tenant context exists. Soft-deleted excluded.
        Eager-loads company + roles to avoid lazy IO in async context."""
        stmt = (
            select(User)
            .where(User.email == email, User.deleted_at.is_(None))
            .options(selectinload(User.company), selectinload(User.roles))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_by_id_unscoped(self, user_id) -> Optional[User]:
        """Used by token refresh / current-user resolution before scope applies."""
        stmt = (
            select(User)
            .where(User.id == user_id, User.deleted_at.is_(None))
            .options(selectinload(User.company), selectinload(User.roles))
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def get_scoped(self, user_id) -> Optional[User]:
        """Tenant-scoped fetch with roles eager-loaded (for management ops)."""
        stmt = (
            self._base_select()
            .where(User.id == user_id)
            .options(selectinload(User.roles))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Email uniqueness check across the platform (emails are global)."""
        stmt = select(User.id).where(
            User.email == email, User.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).first() is not None

    async def search(
        self, *, offset: int, limit: int, search=None, status=None,
        role=None, sort_by="created_at", sort_dir="desc",
    ):
        """Tenant-scoped user search. Returns (rows, total). Roles eager-loaded."""
        stmt = self._base_select().options(selectinload(User.roles))
        if search:
            term = f"%{search.lower()}%"
            stmt = stmt.where(
                func.lower(User.email).like(term)
                | func.lower(func.coalesce(User.first_name, "")).like(term)
                | func.lower(func.coalesce(User.last_name, "")).like(term)
            )
        if status is not None:
            stmt = stmt.where(User.status == status)
        if role is not None:
            stmt = stmt.where(
                User.id.in_(
                    select(UserRole.user_id)
                    .join(Role, Role.id == UserRole.role_id)
                    .where(Role.name == RoleName(role))
                )
            )

        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()

        col = getattr(User, sort_by, User.created_at)
        stmt = stmt.order_by(col.asc() if sort_dir == "asc" else col.desc())
        stmt = stmt.offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    async def get_role(self, role_name: str) -> Optional[Role]:
        stmt = select(Role).where(Role.name == RoleName(role_name))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def set_role(self, user: User, role: Role, *, assigned_by=None) -> None:
        """Replace the user's role set with exactly [role] (single-role model
        for company users). Removes any existing UserRole rows first."""
        existing = (await self.session.execute(
            select(UserRole).where(UserRole.user_id == user.id)
        )).scalars().all()
        for ur in existing:
            await self.session.delete(ur)
        await self.session.flush()
        self.session.add(
            UserRole(user_id=user.id, role_id=role.id, assigned_by=assigned_by)
        )
        await self.session.flush()

    async def count_active_admins(self, company_id, *, exclude_user_id=None) -> int:
        """Active company_admins in a company (for last-admin protection)."""
        stmt = (
            select(func.count(func.distinct(User.id)))
            .select_from(User)
            .join(UserRole, UserRole.user_id == User.id)
            .join(Role, Role.id == UserRole.role_id)
            .where(
                User.company_id == company_id,
                User.status == UserStatus.ACTIVE,
                User.deleted_at.is_(None),
                Role.name == RoleName.COMPANY_ADMIN,
            )
        )
        if exclude_user_id is not None:
            stmt = stmt.where(User.id != exclude_user_id)
        return (await self.session.execute(stmt)).scalar_one()
