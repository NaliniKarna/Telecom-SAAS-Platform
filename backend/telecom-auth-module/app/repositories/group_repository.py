"""Group repository — tenant-scoped via BaseRepository (company_id from ctx).

Membership operations are scoped through the parent group, which is itself
tenant-filtered, so a caller can only touch members of groups in their own
company.
"""
from typing import Optional, Sequence

from sqlalchemy import and_, func, select

from app.models.group import Group, GroupMember
from app.models.user import User
from app.repositories.base import BaseRepository


class GroupRepository(BaseRepository[Group]):
    model = Group
    tenant_scoped = True

    async def search(
        self, *, search: str | None = None, status=None, group_type=None,
        offset: int = 0, limit: int = 20,
    ) -> tuple[Sequence[tuple[Group, int]], int]:
        """Returns (group, member_count) tuples plus the total count."""
        member_count = (
            select(func.count(GroupMember.id))
            .where(GroupMember.group_id == Group.id)
            .correlate(Group)
            .scalar_subquery()
        )
        stmt = self._base_select()
        if search:
            stmt = stmt.where(Group.name.ilike(f"%{search}%"))
        if status is not None:
            stmt = stmt.where(Group.status == status)
        if group_type is not None:
            stmt = stmt.where(Group.group_type == group_type)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = (
            select(Group, member_count.label("member_count"))
            .where(Group.id.in_(select(stmt.subquery().c.id)))
            .order_by(Group.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        return [(r[0], int(r[1] or 0)) for r in rows], total

    async def get_with_member_count(self, group_id) -> Optional[tuple[Group, int]]:
        group = await self.get_by_id(group_id)  # tenant + soft-delete scoped
        if group is None:
            return None
        count = (await self.session.execute(
            select(func.count(GroupMember.id)).where(
                GroupMember.group_id == group_id
            )
        )).scalar_one()
        return group, int(count or 0)

    async def list_members(self, group_id) -> Sequence[tuple[GroupMember, User]]:
        rows = (await self.session.execute(
            select(GroupMember, User)
            .join(User, User.id == GroupMember.user_id)
            .where(GroupMember.group_id == group_id, User.deleted_at.is_(None))
            .order_by(GroupMember.created_at.asc())
        )).all()
        return [(r[0], r[1]) for r in rows]

    async def get_membership(self, group_id, user_id) -> Optional[GroupMember]:
        return (await self.session.execute(
            select(GroupMember).where(and_(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
            ))
        )).scalars().first()

    async def member_ids(self, group_id) -> set:
        rows = (await self.session.execute(
            select(GroupMember.user_id).where(GroupMember.group_id == group_id)
        )).scalars().all()
        return set(rows)

    async def users_in_company(self, user_ids: list, company_id) -> set:
        """Subset of user_ids that actually belong to the given company and are
        not soft-deleted — used to reject cross-tenant member adds."""
        if not user_ids:
            return set()
        rows = (await self.session.execute(
            select(User.id).where(
                User.id.in_(user_ids),
                User.company_id == company_id,
                User.deleted_at.is_(None),
            )
        )).scalars().all()
        return set(rows)
