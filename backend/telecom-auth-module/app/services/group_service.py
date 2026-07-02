"""Group service — organizational groups, tenant-isolated via the repo's ctx.

Groups never grant permissions. The service enforces:
- tenant isolation (the repo is scoped by TenantContext.company_id);
- members must belong to the same company (cross-tenant adds rejected);
- soft-delete on the group removes its membership rows but never the users;
- audit logging on create/update/delete/member-add/member-remove.
"""
import logging
from typing import Any, Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.group import Group, GroupMember
from app.repositories.group_repository import GroupRepository
from app.schemas.group import GroupCreate, GroupUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_ENTITY = "group"


class GroupService:
    def __init__(
        self,
        session: AsyncSession,
        repo: GroupRepository,
        audit: AuditService | None = None,
    ):
        self.session = session
        self.repo = repo
        self.audit = audit or AuditService(session)

    @property
    def _company_id(self):
        # The acting tenant. None only for a super admin (who doesn't use these
        # company-scoped endpoints).
        return self.repo.ctx.company_id if self.repo.ctx else None

    async def list_groups(self, flt, *, offset: int, limit: int):
        return await self.repo.search(
            search=flt.search, status=flt.status, group_type=flt.group_type,
            offset=offset, limit=limit,
        )

    async def get_group(self, group_id) -> tuple[Group, int]:
        res = await self.repo.get_with_member_count(group_id)
        if res is None:
            raise NotFoundError("Group not found")
        return res

    async def create_group(
        self, data: GroupCreate, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> Group:
        if self._company_id is None:
            raise ValidationError("Groups are managed within a company")
        group = await self.repo.create(
            company_id=self._company_id,
            name=data.name,
            description=data.description,
            status=data.status,
            group_type=data.group_type,
        )
        await self.audit.record(
            action="create", entity_type=_ENTITY, entity_id=str(group.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            new_values={
                "name": group.name,
                "status": group.status.value,
                "group_type": group.group_type.value,
            },
        )
        await self.session.commit()
        await self.session.refresh(group)
        return group

    async def update_group(
        self, group_id, data: GroupUpdate, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> tuple[Group, int]:
        group, _ = await self.get_group(group_id)
        patch = data.model_dump(exclude_unset=True)
        if patch:
            before = {}
            for k, v in patch.items():
                old = getattr(group, k)
                before[k] = _s(old)
                setattr(group, k, v)
            await self.session.flush()
            await self.audit.record(
                action="update", entity_type=_ENTITY, entity_id=str(group.id),
                actor_id=actor_id, company_id=self._company_id, ip_address=ip,
                old_values=before, new_values={k: _s(v) for k, v in patch.items()},
            )
            await self.session.commit()
        return await self.get_group(group_id)

    async def delete_group(
        self, group_id, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ) -> None:
        group, _ = await self.get_group(group_id)
        # Remove memberships (hard) — users are untouched — then soft-delete the
        # group itself, consistent with the platform's soft-delete convention.
        await self.session.execute(
            delete(GroupMember).where(GroupMember.group_id == group.id)
        )
        await self.repo.soft_delete(group)
        await self.audit.record(
            action="delete", entity_type=_ENTITY, entity_id=str(group.id),
            actor_id=actor_id, company_id=self._company_id, ip_address=ip,
            old_values={"name": group.name},
        )
        await self.session.commit()

    async def list_members(self, group_id):
        await self.get_group(group_id)  # tenant guard / existence
        return await self.repo.list_members(group_id)

    async def add_members(
        self, group_id, user_ids: list, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ):
        await self.get_group(group_id)  # tenant guard
        # Only users in the same company may be added (reject cross-tenant).
        valid = await self.repo.users_in_company(user_ids, self._company_id)
        invalid = [u for u in user_ids if u not in valid]
        if invalid:
            raise ValidationError(
                "One or more users are not part of this company"
            )
        existing = await self.repo.member_ids(group_id)
        added = []
        for uid in user_ids:
            if uid in existing:
                continue
            self.session.add(GroupMember(group_id=group_id, user_id=uid))
            added.append(str(uid))
        if added:
            await self.session.flush()
            await self.audit.record(
                action="member_added", entity_type=_ENTITY,
                entity_id=str(group_id), actor_id=actor_id,
                company_id=self._company_id, ip_address=ip,
                new_values={"user_ids": added},
            )
            await self.session.commit()
        return await self.repo.list_members(group_id)

    async def remove_member(
        self, group_id, user_id, *, actor_id: Optional[Any] = None,
        ip: Optional[str] = None,
    ):
        await self.get_group(group_id)  # tenant guard
        membership = await self.repo.get_membership(group_id, user_id)
        if membership is None:
            raise NotFoundError("User is not a member of this group")
        await self.session.delete(membership)
        await self.audit.record(
            action="member_removed", entity_type=_ENTITY,
            entity_id=str(group_id), actor_id=actor_id,
            company_id=self._company_id, ip_address=ip,
            old_values={"user_id": str(user_id)},
        )
        await self.session.commit()
        return await self.repo.list_members(group_id)


def _s(v) -> Any:
    return v.value if hasattr(v, "value") else v
