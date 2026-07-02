"""Company user management DTOs.

Scope: a Company Admin managing users within their own company. Role assignment
is restricted at the schema level to company_admin / company_user — super_admin
is never an accepted value, closing the privilege-escalation path at the edge.
"""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.constants import RoleName, UserStatus

# Roles a company admin is allowed to assign. super_admin intentionally absent.
_ASSIGNABLE_ROLES = {RoleName.COMPANY_ADMIN.value, RoleName.COMPANY_USER.value}


def _validate_role(v: str) -> str:
    if v not in _ASSIGNABLE_ROLES:
        raise ValueError(
            f"role must be one of {sorted(_ASSIGNABLE_ROLES)}; "
            "super_admin cannot be assigned"
        )
    return v


def _coerce_role_names(v):
    """Accept ORM Role objects, RoleName enums, or plain strings and return a
    list of role-name strings. Lets UserRead.model_validate(user) work directly
    off the ORM `roles` relationship without the caller pre-flattening it."""
    if v is None:
        return []
    out = []
    for item in v:
        name = getattr(item, "name", item)  # Role -> Role.name; str -> str
        out.append(getattr(name, "value", name))  # RoleName -> value; str -> str
    return out


class UserInvite(BaseModel):
    """Create a user in PENDING state and (conceptually) send an invite."""
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    role: str = Field(default=RoleName.COMPANY_USER.value)

    @field_validator("role")
    @classmethod
    def _role(cls, v: str) -> str:
        return _validate_role(v)


class CompanyAdminInvite(BaseModel):
    """Super-admin bootstrap: invite the first/any admin into a given company.

    Role is fixed to company_admin (this is the bootstrap path); only profile +
    email are accepted. The target company is taken from the URL, never here.
    """
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)


class UserUpdate(BaseModel):
    """Edit profile + role. Email is immutable post-create."""
    model_config = ConfigDict(extra="forbid")
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    role: str | None = None

    @field_validator("role")
    @classmethod
    def _role(cls, v: str | None) -> str | None:
        return _validate_role(v) if v is not None else None


class AcceptInvite(BaseModel):
    """Invitee sets their password via the invite token."""
    model_config = ConfigDict(extra="forbid")
    token: str
    password: str = Field(min_length=8, max_length=128)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    status: UserStatus
    is_email_verified: bool
    roles: list[str] = []
    last_login_at: datetime | None
    created_at: datetime

    @field_validator("roles", mode="before")
    @classmethod
    def _roles_to_names(cls, v):
        return _coerce_role_names(v)


class UserListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    status: UserStatus
    roles: list[str] = []
    created_at: datetime

    @field_validator("roles", mode="before")
    @classmethod
    def _roles_to_names(cls, v):
        return _coerce_role_names(v)


class UserFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    search: str | None = Field(default=None, max_length=255)
    status: UserStatus | None = None
    role: str | None = None
    sort_by: str = Field(default="created_at")
    sort_dir: str = Field(default="desc", pattern="^(asc|desc)$")

    @field_validator("sort_by")
    @classmethod
    def _sort(cls, v: str) -> str:
        allowed = {"created_at", "email", "status"}
        if v not in allowed:
            raise ValueError(f"sort_by must be one of {sorted(allowed)}")
        return v