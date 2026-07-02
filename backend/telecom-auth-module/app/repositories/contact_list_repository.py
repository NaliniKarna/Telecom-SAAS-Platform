"""Contact list repository — tenant-scoped via BaseRepository."""
from typing import Optional, Sequence

from sqlalchemy import and_, func, select

from app.models.contact import Contact, ContactList, ContactListMember
from app.repositories.base import BaseRepository


class ContactListRepository(BaseRepository[ContactList]):
    model = ContactList
    tenant_scoped = True

    async def search(
        self, *, search: str | None = None, offset: int = 0, limit: int = 20,
    ) -> tuple[Sequence[tuple[ContactList, int]], int]:
        member_count = (
            select(func.count(ContactListMember.id))
            .where(ContactListMember.list_id == ContactList.id)
            .correlate(ContactList)
            .scalar_subquery()
        )
        stmt = self._base_select()
        if search:
            stmt = stmt.where(ContactList.name.ilike(f"%{search}%"))
        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = (
            select(ContactList, member_count.label("member_count"))
            .where(ContactList.id.in_(select(stmt.subquery().c.id)))
            .order_by(ContactList.created_at.desc())
            .offset(offset).limit(limit)
        )
        rows = (await self.session.execute(stmt)).all()
        return [(r[0], int(r[1] or 0)) for r in rows], total

    async def get_with_member_count(self, list_id) -> Optional[tuple[ContactList, int]]:
        lst = await self.get_by_id(list_id)  # tenant + soft-delete scoped
        if lst is None:
            return None
        count = (await self.session.execute(
            select(func.count(ContactListMember.id)).where(
                ContactListMember.list_id == list_id
            )
        )).scalar_one()
        return lst, int(count or 0)

    async def list_members(self, list_id) -> Sequence[tuple[ContactListMember, Contact]]:
        rows = (await self.session.execute(
            select(ContactListMember, Contact)
            .join(Contact, Contact.id == ContactListMember.contact_id)
            .where(ContactListMember.list_id == list_id, Contact.deleted_at.is_(None))
            .order_by(ContactListMember.created_at.asc())
        )).all()
        return [(r[0], r[1]) for r in rows]

    async def member_contact_ids(self, list_id) -> set:
        rows = (await self.session.execute(
            select(ContactListMember.contact_id).where(
                ContactListMember.list_id == list_id
            )
        )).scalars().all()
        return set(rows)

    async def get_membership(self, list_id, contact_id) -> Optional[ContactListMember]:
        return (await self.session.execute(
            select(ContactListMember).where(and_(
                ContactListMember.list_id == list_id,
                ContactListMember.contact_id == contact_id,
            ))
        )).scalars().first()

    async def contacts_in_company(self, contact_ids: list, company_id) -> set:
        """Subset of contact_ids that belong to this company and aren't deleted —
        used to reject cross-tenant membership adds."""
        if not contact_ids:
            return set()
        rows = (await self.session.execute(
            select(Contact.id).where(
                Contact.id.in_(contact_ids),
                Contact.company_id == company_id,
                Contact.deleted_at.is_(None),
            )
        )).scalars().all()
        return set(rows)
