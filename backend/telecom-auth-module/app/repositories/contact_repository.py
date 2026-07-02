"""Contact repository — tenant-scoped via BaseRepository (company_id from ctx)."""
from typing import Optional, Sequence

from sqlalchemy import func, or_, select

from app.models.contact import Contact
from app.repositories.base import BaseRepository


class ContactRepository(BaseRepository[Contact]):
    model = Contact
    tenant_scoped = True

    async def search(
        self, *, search: str | None = None, status=None, tag: str | None = None,
        offset: int = 0, limit: int = 20,
    ) -> tuple[Sequence[Contact], int]:
        stmt = self._base_select()
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(
                Contact.first_name.ilike(like),
                Contact.last_name.ilike(like),
                Contact.email.ilike(like),
                Contact.mobile_e164.ilike(like),
                Contact.mobile_raw.ilike(like),
                Contact.landline_e164.ilike(like),
            ))
        if status is not None:
            stmt = stmt.where(Contact.status == status)
        if tag:
            # JSONB array contains the tag.
            stmt = stmt.where(Contact.tags.contains([tag]))

        total = (await self.session.execute(
            select(func.count()).select_from(stmt.subquery())
        )).scalar_one()
        stmt = stmt.order_by(Contact.created_at.desc()).offset(offset).limit(limit)
        rows = (await self.session.execute(stmt)).scalars().all()
        return rows, total

    async def find_duplicate(
        self, *, mobile_e164: str | None, email: str | None,
        exclude_id=None,
    ) -> Optional[Contact]:
        """A duplicate within the company shares a normalized mobile or email."""
        clauses = []
        if mobile_e164:
            clauses.append(Contact.mobile_e164 == mobile_e164)
        if email:
            clauses.append(func.lower(Contact.email) == email.lower())
        if not clauses:
            return None
        stmt = self._base_select().where(or_(*clauses))
        if exclude_id is not None:
            stmt = stmt.where(Contact.id != exclude_id)
        return (await self.session.execute(stmt.limit(1))).scalars().first()
