"""Idempotent seed: system roles, permission catalog, role->permission mappings,
and a bootstrap super admin. Safe to run repeatedly."""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ROLE_PERMISSIONS, Permission as PermEnum, RoleName
from app.core.security import hash_password
from app.models.role import Permission, Role, RolePermission
from app.models.user import User, UserRole
from app.core.constants import UserStatus

logger = logging.getLogger(__name__)

_ROLE_LABELS = {
    RoleName.SUPER_ADMIN: "Super Admin",
    RoleName.COMPANY_ADMIN: "Company Admin",
    RoleName.COMPANY_USER: "Company User",
}


async def seed_permissions(session: AsyncSession) -> dict[str, Permission]:
    existing = {
        p.code: p for p in (await session.execute(select(Permission))).scalars()
    }
    for perm in PermEnum:
        if perm.value not in existing:
            obj = Permission(id=uuid.uuid4(), code=perm.value)
            session.add(obj)
            existing[perm.value] = obj
    await session.flush()
    return existing


async def seed_roles(session: AsyncSession) -> dict[RoleName, Role]:
    existing = {
        r.name: r for r in (await session.execute(select(Role))).scalars()
    }
    for role_name in RoleName:
        if role_name not in existing:
            obj = Role(
                id=uuid.uuid4(),
                name=role_name,
                label=_ROLE_LABELS[role_name],
            )
            session.add(obj)
            existing[role_name] = obj
    await session.flush()
    return existing


async def seed_role_permissions(
    session: AsyncSession,
    roles: dict[RoleName, Role],
    permissions: dict[str, Permission],
) -> None:
    existing = {
        (rp.role_id, rp.permission_id)
        for rp in (await session.execute(select(RolePermission))).scalars()
    }
    for role_name, perm_set in ROLE_PERMISSIONS.items():
        role = roles[role_name]
        for perm in perm_set:
            pid = permissions[perm.value].id
            if (role.id, pid) not in existing:
                session.add(RolePermission(role_id=role.id, permission_id=pid))
    await session.flush()


async def seed_super_admin(
    session: AsyncSession,
    roles: dict[RoleName, Role],
    email: str,
    password: str,
) -> None:
    found = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if found is not None:
        return
    admin = User(
        id=uuid.uuid4(),
        company_id=None,  # platform-level
        email=email,
        hashed_password=hash_password(password),
        first_name="Super",
        last_name="Admin",
        status=UserStatus.ACTIVE,
        is_email_verified=True,
    )
    session.add(admin)
    await session.flush()
    session.add(
        UserRole(user_id=admin.id, role_id=roles[RoleName.SUPER_ADMIN].id)
    )
    logger.info("seeded super admin: %s", email)


async def run_seed(
    session: AsyncSession,
    super_admin_email: str = "admin@example.com",
    super_admin_password: str = "ChangeMe123!",
) -> None:
    permissions = await seed_permissions(session)
    roles = await seed_roles(session)
    await seed_role_permissions(session, roles, permissions)
    await seed_super_admin(
        session, roles, super_admin_email, super_admin_password
    )
    await session.commit()
