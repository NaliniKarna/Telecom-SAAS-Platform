"""Profile service (all roles, self-service).

A user edits only their OWN profile — the acting user object is passed in by the
route from the authenticated token; there is no user id in the request, so a
user can never edit anyone else. Email, roles, and status are never touched here
(email is the login identity; roles/status are admin-managed). Password changes
are handled by the existing AuthService.change_password — not duplicated here.
"""
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.auth import ProfileUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_ENTITY = "profile"
_EDITABLE = ("first_name", "last_name")


class ProfileService:
    def __init__(self, session: AsyncSession, audit: AuditService | None = None):
        self.session = session
        self.audit = audit or AuditService(session)

    async def update_profile(
        self, user: User, data: ProfileUpdate, *,
        ip: Optional[str] = None,
    ) -> User:
        patch = {
            k: v for k, v in data.model_dump(exclude_unset=True).items()
            if k in _EDITABLE
        }
        if patch:
            before = {k: getattr(user, k) for k in patch}
            for k, v in patch.items():
                setattr(user, k, v)
            await self.audit.record(
                action="update", entity_type=_ENTITY, entity_id=str(user.id),
                actor_id=user.id, company_id=user.company_id, ip_address=ip,
                old_values=before, new_values=patch,
            )
            await self.session.commit()
            await self.session.refresh(user)
        return user

    async def set_avatar(
        self, user: User, avatar_url: str, *, ip: Optional[str] = None,
    ) -> User:
        old = user.avatar_url
        user.avatar_url = avatar_url
        await self.audit.record(
            action="update_avatar", entity_type=_ENTITY, entity_id=str(user.id),
            actor_id=user.id, company_id=user.company_id, ip_address=ip,
            old_values={"avatar_url": old}, new_values={"avatar_url": avatar_url},
        )
        await self.session.commit()
        await self.session.refresh(user)
        return user
