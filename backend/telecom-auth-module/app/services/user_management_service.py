"""Company user management use cases (Company Admin scope).

Enforces, in one place:
- Invite flow: new users are created PENDING with no usable password; they set
  it via an invite token (reuses the password-reset token mechanism — no auth
  redesign). accept_invite activates the account.
- Role restriction: only company_admin / company_user assignable (schema also
  guards this); super_admin can never be set here.
- Self-protection: an admin cannot deactivate/delete their own account or strip
  their own company_admin role, and the last active company_admin in a company
  cannot be deactivated or deleted.
- Tenant isolation: every lookup goes through the tenant-scoped repository, so
  an admin can only ever see/modify users in their own company.

The service receives the acting user's id + company_id explicitly and never
trusts a client-supplied company id.
"""
import logging
import secrets
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleName, UserStatus
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.security import (
    create_invite_token,
    create_password_reset_token,
    decode_token,
    hash_password,
)
from app.core.constants import TokenType
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import AcceptInvite, UserFilter, UserInvite, UserUpdate
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

_ENTITY = "user"


class UserManagementService:
    def __init__(
        self,
        session: AsyncSession,
        repo: UserRepository,
        audit: AuditService | None = None,
    ):
        self.session = session
        self.users = repo
        self.audit = audit or AuditService(session)

    # ----- reads (tenant-scoped via repo) -----------------------------------
    async def list_users(
        self, *, offset: int, limit: int, filters: UserFilter | None = None
    ) -> tuple[Sequence[User], int]:
        f = filters or UserFilter()
        return await self.users.search(
            offset=offset, limit=limit, search=f.search, status=f.status,
            role=f.role, sort_by=f.sort_by, sort_dir=f.sort_dir,
        )

    async def get_user(self, user_id) -> User:
        user = await self.users.get_scoped(user_id)
        if user is None:
            # Either doesn't exist or belongs to another company — same answer,
            # so we never leak cross-tenant existence.
            raise NotFoundError("User not found")
        return user

    # ----- invite / create --------------------------------------------------
    async def invite_user(
        self, data: UserInvite, *, company_id, actor_id, ip=None
    ) -> tuple[User, str]:
        if await self.users.email_exists(data.email):
            raise ConflictError(f"A user with email '{data.email}' already exists")

        role = await self.users.get_role(data.role)
        if role is None:
            raise ValidationError(f"Unknown role: {data.role}")

        # PENDING user with an unusable random password (replaced on accept).
        user = await self.users.create(
            company_id=company_id,
            email=data.email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            first_name=data.first_name,
            last_name=data.last_name,
            status=UserStatus.PENDING,
            is_email_verified=False,
        )
        await self.users.set_role(user, role, assigned_by=actor_id)
        token = create_invite_token(str(user.id))
        await self.audit.record(
            action="invite", entity_type=_ENTITY, entity_id=user.id,
            actor_id=actor_id, company_id=company_id, ip_address=ip,
            new_values={"email": user.email, "role": data.role},
        )
        await self.session.commit()
        await self.session.refresh(user)
        return user, token

    async def invite_company_admin(
        self, company_id, email, first_name=None, last_name=None, *,
        actor_id, ip=None,
    ) -> tuple[User, str]:
        """Super-admin bootstrap: create a PENDING company_admin in a specific
        company and return an invite token. Uses an explicit company_id (never a
        tenant context), so it works for a super admin who has no company of
        their own. Verifies the company exists and is not soft-deleted.
        """
        from app.models.company import Company

        company = await self.session.get(Company, company_id)
        if company is None or company.deleted_at is not None:
            raise NotFoundError("Company not found")

        if await self.users.email_exists(email):
            raise ConflictError(f"A user with email '{email}' already exists")

        role = await self.users.get_role(RoleName.COMPANY_ADMIN.value)
        if role is None:
            raise ValidationError("company_admin role is not configured")

        user = await self.users.create(
            company_id=company_id,
            email=email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            first_name=first_name,
            last_name=last_name,
            status=UserStatus.PENDING,
            is_email_verified=False,
        )
        await self.users.set_role(user, role, assigned_by=actor_id)
        token = create_invite_token(str(user.id))
        await self.audit.record(
            action="invite_admin", entity_type=_ENTITY, entity_id=user.id,
            actor_id=actor_id, company_id=company_id, ip_address=ip,
            new_values={"email": user.email, "role": RoleName.COMPANY_ADMIN.value},
        )
        await self.session.commit()
        await self.session.refresh(user)
        return user, token

    async def accept_invite(self, data: AcceptInvite) -> User:
        """Invitee sets their password; account becomes ACTIVE + verified.
        Pre-auth (no tenant context) so uses an unscoped fetch."""
        payload = decode_token(data.token, TokenType.PASSWORD_RESET)
        user = await self.users.get_by_id_unscoped(payload.get("sub"))
        if user is None:
            raise NotFoundError("Invalid invite")
        if user.status != UserStatus.PENDING:
            raise ValidationError("This invite has already been used")
        user.hashed_password = hash_password(data.password)
        user.status = UserStatus.ACTIVE
        user.is_email_verified = True
        await self.session.flush()
        await self.audit.record(
            action="accept_invite", entity_type=_ENTITY, entity_id=user.id,
            actor_id=user.id, company_id=user.company_id,
        )
        await self.session.commit()
        await self.session.refresh(user)
        return user

    # ----- update / role ----------------------------------------------------
    async def update_user(
        self, user_id, data: UserUpdate, *, company_id, actor_id, ip=None
    ) -> User:
        user = await self.get_user(user_id)
        patch = data.model_dump(exclude_unset=True)
        new_role = patch.pop("role", None)

        # Self-protection: can't strip your own company_admin role.
        if (
            new_role is not None
            and user.id == actor_id
            and RoleName.COMPANY_ADMIN.value in user.role_names
            and new_role != RoleName.COMPANY_ADMIN.value
        ):
            raise PermissionDeniedError(
                "You cannot remove your own company_admin role"
            )

        # Last-admin protection: demoting the last active admin is blocked.
        if (
            new_role is not None
            and RoleName.COMPANY_ADMIN.value in user.role_names
            and new_role != RoleName.COMPANY_ADMIN.value
            and user.status == UserStatus.ACTIVE
        ):
            remaining = await self.users.count_active_admins(
                company_id, exclude_user_id=user.id
            )
            if remaining == 0:
                raise PermissionDeniedError(
                    "Cannot demote the last active company admin"
                )

        if patch:
            await self.users.update(user, **patch)
        if new_role is not None:
            role = await self.users.get_role(new_role)
            if role is None:
                raise ValidationError(f"Unknown role: {new_role}")
            await self.users.set_role(user, role, assigned_by=actor_id)

        await self.audit.record(
            action="update", entity_type=_ENTITY, entity_id=user.id,
            actor_id=actor_id, company_id=company_id, ip_address=ip,
            new_values={**patch, **({"role": new_role} if new_role else {})},
        )
        await self.session.commit()
        return await self.get_user(user_id)

    # ----- activate / deactivate --------------------------------------------
    async def set_active(
        self, user_id, active: bool, *, company_id, actor_id, ip=None
    ) -> User:
        user = await self.get_user(user_id)

        if not active:
            if user.id == actor_id:
                raise PermissionDeniedError("You cannot deactivate your own account")
            await self._guard_last_admin(user, company_id)

        user.status = UserStatus.ACTIVE if active else UserStatus.INACTIVE
        await self.users.update(user, status=user.status)
        await self.audit.record(
            action="activate" if active else "deactivate",
            entity_type=_ENTITY, entity_id=user.id, actor_id=actor_id,
            company_id=company_id, ip_address=ip,
        )
        await self.session.commit()
        return await self.get_user(user_id)

    # ----- delete -----------------------------------------------------------
    async def delete_user(self, user_id, *, company_id, actor_id, ip=None) -> None:
        user = await self.get_user(user_id)
        if user.id == actor_id:
            raise PermissionDeniedError("You cannot delete your own account")
        await self._guard_last_admin(user, company_id)
        await self.users.soft_delete(user)
        await self.audit.record(
            action="delete", entity_type=_ENTITY, entity_id=user_id,
            actor_id=actor_id, company_id=company_id, ip_address=ip,
        )
        await self.session.commit()

    # ----- helpers ----------------------------------------------------------
    async def _guard_last_admin(self, user: User, company_id) -> None:
        """Block removing/deactivating the last active company_admin."""
        if (
            RoleName.COMPANY_ADMIN.value in user.role_names
            and user.status == UserStatus.ACTIVE
        ):
            remaining = await self.users.count_active_admins(
                company_id, exclude_user_id=user.id
            )
            if remaining == 0:
                raise PermissionDeniedError(
                    "Cannot remove the last active company admin"
                )