"""Dependency injection composition root + RBAC guards.

Assembles the request-scoped dependency chain:
  get_db -> token payload -> tenant context -> current user -> repos -> services
and exposes parameterized authorization guards.
"""
from typing import TYPE_CHECKING, Annotated, Callable

if TYPE_CHECKING:
    from app.services.ai_voice_service import AdminAiVoiceService, AiVoiceService
    from app.services.missed_call_service import MissedCallService
    from app.services.tts_usage_service import TtsUsageService
    from app.services.voice_campaign_service import VoiceCampaignService
    from app.services.ai_voice_service import VoiceTemplateService

from fastapi import Depends, Request
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
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
from app.core.http import client_ip as _request_client_ip
from app.repositories.company_repository import CompanyRepository
from app.services.company_settings_service import CompanySettingsService
from app.services.change_request_service import ChangeRequestService
from app.services.group_service import GroupService
from app.core.config import settings
from app.core.rate_limit import api_key_request_limiter, ip_auth_lockout
from app.services.api_key_service import (
    ApiKeyContext,
    ApiKeyService,
    audit_ip_lockout,
    audit_key_rate_limited,
    authenticate_api_key,
)
from app.services.contact_service import ContactService
from app.services.contact_import_service import ContactImportService
from app.services.telephony_service import TelephonyService
from app.services.voice_service import VoiceService
from app.repositories.telephony_repository import TelephonyConnectionRepository
from app.services.registration_service import RegistrationService
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
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

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
# API-key authentication chain (programmatic access, no human user)
#
# Separate from the JWT chain above: the Angular console authenticates with a
# bearer token; external/programmatic callers authenticate with an X-API-Key
# header. Only routes that explicitly declare CurrentApiKey accept this
# scheme — no JWT-protected route (CurrentUser/CurrentContext) is reachable
# with an API key, and vice versa. This is the live enforcement point for
# ApiKeyService.is_ip_allowed(), plus abuse protection layered on top:
#   1. an IP already locked out from repeated invalid-key attempts is
#      rejected before touching the DB at all,
#   2. authenticate_api_key() does the real lookup (status + IP whitelist),
#   3. a failure here counts toward that IP's lockout; a success clears it,
#   4. a per-key sliding-window limit caps request volume from a *valid* key
#      (protects against a leaked-but-real key being hammered).
# See app/core/rate_limit.py for why this is in-process, not Redis-backed.
# --------------------------------------------------------------------------- #
async def get_api_key_context(
    request: Request,
    db: DbSession,
    presented_key: Annotated[str | None, Depends(_api_key_header)],
) -> ApiKeyContext:
    ip = _request_client_ip(request)

    if ip and await ip_auth_lockout.is_locked(ip):
        raise PermissionDeniedError(
            "Too many failed API key attempts from this address. Try again later."
        )

    if not presented_key:
        raise AuthenticationError("Missing API key")

    try:
        ctx = await authenticate_api_key(db, presented_key, client_ip=ip)
    except AuthenticationError:
        # Unknown/revoked/expired key — this is exactly the signal a
        # brute-force/enumeration attempt looks like, so it counts toward
        # the IP's lockout. IP-whitelist mismatches (PermissionDeniedError,
        # raised by authenticate_api_key itself) are audited there instead
        # and don't count here — that's a valid key from an unexpected
        # place, not credential guessing.
        if ip:
            just_locked = await ip_auth_lockout.register_failure(
                ip,
                limit=settings.API_KEY_AUTH_FAILURE_LIMIT,
                window_seconds=settings.API_KEY_AUTH_FAILURE_WINDOW_SECONDS,
                lockout_seconds=settings.API_KEY_AUTH_LOCKOUT_SECONDS,
            )
            if just_locked:
                await audit_ip_lockout(db, ip)
        raise

    if ip:
        await ip_auth_lockout.register_success(ip)

    allowed = await api_key_request_limiter.allow(
        str(ctx.key_id),
        limit=settings.API_KEY_REQUEST_LIMIT_PER_MINUTE,
        window_seconds=60,
    )
    if not allowed:
        await audit_key_rate_limited(db, ctx, ip)
        raise PermissionDeniedError("API key request rate limit exceeded")

    return ctx


CurrentApiKey = Annotated[ApiKeyContext, Depends(get_api_key_context)]


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


def get_ai_voice_service(db: DbSession, ctx: CurrentContext) -> "AiVoiceService":
    from app.services.ai_voice_service import AiVoiceService
    return AiVoiceService(db, ctx, AuditService(db))


def get_voice_template_service(db: DbSession, ctx: CurrentContext) -> "VoiceTemplateService":
    from app.services.ai_voice_service import VoiceTemplateService
    from app.services.tts_usage_service import TtsUsageService
    return VoiceTemplateService(db, ctx, AuditService(db), TtsUsageService(db))


def get_tts_usage_service(db: DbSession) -> "TtsUsageService":
    from app.services.tts_usage_service import TtsUsageService
    return TtsUsageService(db)


def get_voice_campaign_service(db: DbSession, ctx: CurrentContext) -> "VoiceCampaignService":
    from app.services.voice_campaign_service import VoiceCampaignService
    return VoiceCampaignService(db, ctx, AuditService(db))


def get_admin_ai_voice_service(db: DbSession) -> "AdminAiVoiceService":
    # No CurrentContext dependency here — this service is platform-scoped
    # (no tenant/company concept at all), and the route layer gates access
    # via require_role(SUPER_ADMIN) directly, not via a permission check
    # that would otherwise pull CurrentContext in anyway.
    from app.services.ai_voice_service import AdminAiVoiceService
    return AdminAiVoiceService(db, AuditService(db))


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


def get_telephony_service(db: DbSession, ctx: CurrentContext) -> "TelephonyService":
    # Explicitly scoped in the repo (mixes platform-level + per-tenant rows), so
    # the service reads scope from repo.ctx rather than the base tenant filter.
    return TelephonyService(
        db, TelephonyConnectionRepository(db, ctx), AuditService(db)
    )


def get_registration_service(db: DbSession) -> "RegistrationService":
    # Public + platform-level (no tenant context): register is pre-auth, and
    # approve/reject are super-admin actions that pass the reviewer explicitly.
    return RegistrationService(db, audit=AuditService(db))


def get_voice_service(db: DbSession, ctx: CurrentContext) -> "VoiceService":
    """Factory for the Voice Platform service.

    Injects three repositories:
      - VoiceExtensionRepository (tenant-scoped)
      - VoiceCallLogRepository   (tenant-scoped)
      - TelephonyConnectionRepository (platform-level; used for connection resolution)
    """
    from app.repositories.voice_repository import (
        VoiceCallLogRepository,
        VoiceExtensionRepository,
    )
    return VoiceService(
        db,
        VoiceExtensionRepository(db, ctx),
        VoiceCallLogRepository(db, ctx),
        TelephonyConnectionRepository(db, ctx),
        AuditService(db),
    )


def get_missed_call_service(
    db: DbSession, ctx: CurrentContext
) -> "MissedCallService":
    """Factory for the Missed Call Platform service."""
    from app.repositories.missed_call_repository import MissedCallRepository
    from app.services.missed_call_service import MissedCallService

    return MissedCallService(
        db,
        MissedCallRepository(db, ctx),
        AuditService(db),
    )
