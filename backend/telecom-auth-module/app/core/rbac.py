"""RBAC resolution helpers and the per-request TenantContext."""
from dataclasses import dataclass, field

from app.core.constants import ROLE_PERMISSIONS, Permission, RoleName


def resolve_permissions(role_names: list[str]) -> set[str]:
    """Union of permissions across all assigned roles."""
    perms: set[Permission] = set()
    for name in role_names:
        try:
            role = RoleName(name)
        except ValueError:
            continue
        perms |= ROLE_PERMISSIONS.get(role, set())
    return {p.value for p in perms}


@dataclass
class TenantContext:
    """Authenticated request context derived from the validated access token.

    company_id is None for platform super admins. The repository layer reads
    company_id from here (never from client input) to enforce tenant isolation.
    """

    user_id: str
    company_id: str | None
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    @property
    def is_super_admin(self) -> bool:
        return RoleName.SUPER_ADMIN.value in self.roles

    def has_permission(self, permission: str) -> bool:
        if self.is_super_admin:
            return True
        return permission in self.permissions

    def has_role(self, role: str) -> bool:
        return role in self.roles
