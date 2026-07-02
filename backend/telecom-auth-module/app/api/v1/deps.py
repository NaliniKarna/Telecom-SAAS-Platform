"""Dependency injection composition root + RBAC guards.

Assembles the request-scoped dependency chain:
  get_db -> token payload -> tenant context -> current user -> repos -> services
and exposes parameterized authorization guards.
"""
from typing import Annotated, Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.audit_service import AuditService
from app.services.sms_campaign_service import SmsCampaignService
from app.services.sms_analytics_service import SmsAnalyticsService
from app.services.user_management_service import UserManagementService

from app.core.constants import TokenType
from app.core.exceptions import (
    AuthenticationError,
    InactiveAccountError,
    PermissionDeniedError,
)
from app.repositories.company_repository import CompanyRepository
from app.services.company_settings_service import CompanySettingsService
from app.services.change_request_service import ChangeRequestService
from app.services.group_service import GroupService
from app.services.api_key_service import ApiKeyService
from app.services.contact_service import ContactService
from app.services.contact_import_service import ContactImportService
from app.services.contact_list_service import ContactListService
from app.repositories.contact_repository import ContactRepository
from app.repositories.contact_list_repository import ContactListRepository
from app.repositories.api_key_repository import ApiKeyRepository
from app.repositories.group_repository import GroupRepository
from app.services.company_service import CompanyService
from app.repositories.subscription_plan import SubscriptionPlanRepository
from app.services.subscription_plan_service import SubscriptionPlanService
from app.repositories.audit_log_repository import AuditLogRepository
from app.services.audit_log_service import AuditLogService
from app.services.audit_service import AuditService
from app.services.dashboard_service import DashboardService
from app.services.company_dashboard_service import CompanyDashboardService
from app.services.profile_service import ProfileService
from app.services.platform_settings_service import PlatformSettingsService
from app.services.sms_service import SmsService
from app.core.rbac import TenantContext, resolve_permissions
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


# --------------------------------------------------------------------------- #
# Authentication chain
# --------------------------------------------------------------------------- #
async def get_token_payload(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer)
    ],
) -> dict:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Not authenticated")
    return decode_token(credentials.credentials, TokenType.ACCESS)


async def get_tenant_context(
    payload: Annotated[dict, Depends(get_token_payload)],
) -> TenantContext:
    roles = payload.get("roles", [])
    # Permissions in the token are a convenience; we re-resolve from roles as
    # the source of truth so a permission-map change takes effect immediately.
    permissions = resolve_permissions(roles)
    return TenantContext(
        user_id=payload["sub"],
        company_id=payload.get("company_id"),
        roles=roles,
        permissions=permissions,
    )


async def get_current_user(
    db: DbSession,
    ctx: Annotated[TenantContext, Depends(get_tenant_context)],
) -> User:
    repo = UserRepository(db, ctx)
    user = await repo.get_by_id_unscoped(ctx.user_id)
    if user is None:
        raise AuthenticationError("User no longer exists")
    if not user.is_active:
        raise InactiveAccountError("Account is not active")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentContext = Annotated[TenantContext, Depends(get_tenant_context)]


# --------------------------------------------------------------------------- #
# Repository / service providers
# --------------------------------------------------------------------------- #
def get_user_repository(db: DbSession, ctx: CurrentContext) -> UserRepository:
    return UserRepository(db, ctx)


def get_auth_service(db: DbSession) -> AuthService:
    # Auth service operates pre-context (login/refresh), so no tenant ctx.
    return AuthService(db, UserRepository(db), RefreshTokenRepository(db))

def get_company_service(db: DbSession) -> "CompanyService":
    return CompanyService(db, CompanyRepository(db), AuditService(db))


def get_change_request_service(db: DbSession) -> "ChangeRequestService":
    return ChangeRequestService(db, CompanyRepository(db), AuditService(db))


def get_company_settings_service(db: DbSession) -> "CompanySettingsService":
    audit = AuditService(db)
    repo = CompanyRepository(db)
    return CompanySettingsService(
        db, repo, audit, ChangeRequestService(db, repo, audit)
    )

def get_plan_service(db: DbSession) -> "SubscriptionPlanService":
    return SubscriptionPlanService(
        db, SubscriptionPlanRepository(db), AuditService(db)
    )

def get_audit_log_service(db: DbSession) -> "AuditLogService":
    return AuditLogService(db, AuditLogRepository(db))

def get_dashboard_service(db: DbSession) -> "DashboardService":
    return DashboardService(db)


def get_company_dashboard_service(db: DbSession) -> "CompanyDashboardService":
    return CompanyDashboardService(db)

def get_platform_settings_service(db: DbSession) -> "PlatformSettingsService":
    return PlatformSettingsService(db, AuditService(db))


def get_sms_service(db: DbSession, ctx: CurrentContext) -> "SmsService":
    return SmsService(db, ctx, AuditService(db))


def get_sms_campaign_service(db: DbSession, ctx: CurrentContext) -> "SmsCampaignService":
    return SmsCampaignService(db, ctx, AuditService(db))


def get_sms_analytics_service(db: DbSession, ctx: CurrentContext) -> "SmsAnalyticsService":
    return SmsAnalyticsService(db, ctx, AuditService(db))

def get_user_management_service(
    db: DbSession, ctx: CurrentContext
) -> "UserManagementService":
    return UserManagementService(db, get_user_repository(db, ctx), AuditService(db))


def get_public_user_management_service(
    db: DbSession,
) -> "UserManagementService":
    """Context-free service for PRE-AUTH endpoints (e.g. accept-invite), where
    the caller has no access token yet. Uses an unscoped repository — safe here
    because accept_invite looks the user up by the invite token's subject, not
    by tenant scope."""
    return UserManagementService(db, UserRepository(db, None), AuditService(db))


# --------------------------------------------------------------------------- #
# RBAC guards (parameterized dependencies)
# --------------------------------------------------------------------------- #
def require_permission(*permissions: str) -> Callable:
    """Guard: caller must hold ALL listed permissions (super admin bypasses)."""

    async def _guard(ctx: CurrentContext) -> TenantContext:
        for perm in permissions:
            if not ctx.has_permission(perm):
                raise PermissionDeniedError(
                    f"Missing required permission: {perm}"
                )
        return ctx

    return _guard


def require_role(*roles: str) -> Callable:
    """Guard: caller must hold at least one of the listed roles."""

    async def _guard(ctx: CurrentContext) -> TenantContext:
        if ctx.is_super_admin:
            return ctx
        if not any(ctx.has_role(r) for r in roles):
            raise PermissionDeniedError("Insufficient role")
        return ctx

    return _guard


def get_profile_service(db: DbSession) -> "ProfileService":
    return ProfileService(db, AuditService(db))


def get_group_service(db: DbSession, ctx: CurrentContext) -> "GroupService":
    # Tenant-scoped: the repo filters by ctx.company_id, so a company admin only
    # ever sees/touches groups in their own company.
    return GroupService(db, GroupRepository(db, ctx), AuditService(db))


def get_api_key_service(db: DbSession, ctx: CurrentContext) -> "ApiKeyService":
    # Tenant-scoped: the repo filters by ctx.company_id.
    return ApiKeyService(db, ApiKeyRepository(db, ctx), AuditService(db))


def get_contact_service(db: DbSession, ctx: CurrentContext) -> "ContactService":
    return ContactService(db, ContactRepository(db, ctx), AuditService(db))


def get_contact_list_service(db: DbSession, ctx: CurrentContext) -> "ContactListService":
    return ContactListService(db, ContactListRepository(db, ctx), AuditService(db))


def get_contact_import_service(db: DbSession, ctx: CurrentContext) -> "ContactImportService":
    return ContactImportService(db, ContactRepository(db, ctx), AuditService(db))
