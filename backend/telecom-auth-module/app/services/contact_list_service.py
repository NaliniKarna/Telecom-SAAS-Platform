"""Contact list service — company-scoped, tenant-isolated via the repo's ctx.

Mirrors the group_service pattern: CRUD + membership add/remove, audited;
delete removes memberships only (contacts untouched); cross-tenant contact-add
rejected.
"""
import logging
from typing import Any, Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.contact import ContactList, ContactListMember
from app.repositories.contact_list_repository import ContactListRepository
from app.schemas.contact import ContactListCreate, ContactListUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_ENTITY = "contact_list"


class ContactListService:
    def __init__(
        self, session: AsyncSession, repo: ContactListRepository,
        audit: AuditService | None = None,
    ):
        self.session = session
        self.repo = repo
        self.audit = audit or AuditService(session)

    @property
    def _company_id(self):
        return self.repo.ctx.company_id if self.repo.ctx else None

    async def list_lists(self, *, search, offset, limit):
        return await self.repo.search(search=search, offset=offset, limit=limit)

    async def get_list(self, list_id) -> tuple[ContactList, int]:
        res = await self.repo.get_with_member_count(list_id)
        if res is None:
            raise NotFoundError("Contact list not found")
        return res

    async def create_list(
        self, data: ContactListCreate, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> ContactList:
        if self._company_id is None:
            raise ValidationError("Contact lists are managed within a company")
        lst = await self.repo.create(
            company_id=self._company_id, name=data.name, description=data.description,
        )
        await self.audit.record(
            action="create", entity_type=_ENTITY, entity_id=str(lst.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            new_values={"name": lst.name},
        )
        await self.session.commit()
        await self.session.refresh(lst)
        return lst

    async def update_list(
        self, list_id, data: ContactListUpdate, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> tuple[ContactList, int]:
        lst, _ = await self.get_list(list_id)
        patch = data.model_dump(exclude_unset=True)
        if patch:
            before = {k: getattr(lst, k) for k in patch}
            for k, v in patch.items():
                setattr(lst, k, v)
            await self.session.flush()
            await self.audit.record(
                action="update", entity_type=_ENTITY, entity_id=str(lst.id),
                actor_id=actor_id, company_id=self._company_id, ip_address=ip,
                old_values=before, new_values=patch,
            )
            await self.session.commit()
        return await self.get_list(list_id)

    async def delete_list(
        self, list_id, *, actor_id: Optional[Any] = None, ip: Optional[str] = None,
    ) -> None:
        lst, _ = await self.get_list(list_id)
        # Remove memberships (hard); contacts are untouched. Soft-delete the list.
        await self.session.execute(
            delete(ContactListMember).where(ContactListMember.list_id == lst.id)
        )
        await self.repo.soft_delete(lst)
        await self.audit.record(
            action="delete", entity_type=_ENTITY, entity_id=str(lst.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            old_values={"name": lst.name},
        )
        await self.session.commit()

    async def list_members(self, list_id):
        await self.get_list(list_id)  # tenant guard
        return await self.repo.list_members(list_id)

    async def add_contacts(
        self, list_id, contact_ids: list, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ):
        await self.get_list(list_id)  # tenant guard
        valid = await self.repo.contacts_in_company(contact_ids, self._company_id)
        invalid = [c for c in contact_ids if c not in valid]
        if invalid:
            raise ValidationError("One or more contacts are not part of this company")
        existing = await self.repo.member_contact_ids(list_id)
        added = []
        for cid in contact_ids:
            if cid in existing:
                continue
            self.session.add(ContactListMember(list_id=list_id, contact_id=cid))
            added.append(str(cid))
        if added:
            await self.session.flush()
            await self.audit.record(
                action="contacts_added", entity_type=_ENTITY, entity_id=str(list_id),
                actor_id=actor_id, company_id=self._company_id, ip_address=ip,
                new_values={"contact_ids": added},
            )
            await self.session.commit()
        return await self.repo.list_members(list_id)

    async def remove_contact(
        self, list_id, contact_id, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ):
        await self.get_list(list_id)  # tenant guard
        membership = await self.repo.get_membership(list_id, contact_id)
        if membership is None:
            raise NotFoundError("Contact is not in this list")
        await self.session.delete(membership)
        await self.audit.record(
            action="contact_removed", entity_type=_ENTITY, entity_id=str(list_id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            old_values={"contact_id": str(contact_id)},
        )
        await self.session.commit()
        return await self.repo.list_members(list_id)
