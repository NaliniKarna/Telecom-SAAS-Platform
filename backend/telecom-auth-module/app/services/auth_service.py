"""Authentication use cases: login, token refresh/rotation, logout, password mgmt.

The service owns transaction boundaries and raises domain exceptions only.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.constants import CompanyStatus, TokenType, UserStatus
from app.core.exceptions import (
    AccountLockedError,
    AuthenticationError,
    InactiveAccountError,
    NotFoundError,
    ValidationError,
)
from app.core.rbac import resolve_permissions
from app.core.security import (
    create_access_token,
    create_password_reset_token,
    create_email_verification_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_secret,
    password_needs_rehash,
    verify_password,
)
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

# Generic message — never reveal whether the email or the password was wrong.
_INVALID_CREDENTIALS = "Invalid email or password"


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        user_repo: UserRepository,
        refresh_repo: RefreshTokenRepository,
    ):
        self.session = session
        self.users = user_repo
        self.refresh = refresh_repo
        # Lightweight audit hooks. Self-constructed from the session so existing
        # callers need no change. Recording never blocks the auth flow.
        self.audit = AuditService(session)

    async def _audit_auth(
        self, action: str, *, user: User | None = None, ip: str | None = None,
        description: str | None = None,
    ) -> None:
        """Record an auth event. Best-effort: failures here must not break auth."""
        try:
            await self.audit.record(
                action=action, entity_type="auth",
                entity_id=str(user.id) if user else None,
                actor_id=user.id if user else None,
                company_id=user.company_id if user else None,
                ip_address=ip, description=description,
            )
        except Exception:  # noqa: BLE001 - audit must never break login
            logger.warning("auth_audit_failed", extra={"action": action})

    # ----- login ------------------------------------------------------------
    async def login(
        self, email: str, password: str, *, ip: str | None = None
    ) -> TokenResponse:
        user = await self.users.get_by_email(email)

        # Constant-ish work even when user is missing, to blunt enumeration.
        if user is None:
            # Run a dummy verify to keep timing comparable, then fail generically.
            verify_password(password, hash_password("dummy"))
            await self._audit_auth(
                "login_failed", ip=ip, description=f"unknown email: {email}"
            )
            await self.session.commit()
            raise AuthenticationError(_INVALID_CREDENTIALS)

        if user.status == UserStatus.LOCKED:
            await self._audit_auth(
                "login_failed", user=user, ip=ip, description="account locked"
            )
            await self.session.commit()
            raise AccountLockedError(
                "Account locked due to too many failed login attempts"
            )

        if not verify_password(password, user.hashed_password):
            await self._register_failed_login(user)
            await self._audit_auth(
                "login_failed", user=user, ip=ip, description="invalid password"
            )
            await self.session.commit()
            raise AuthenticationError(_INVALID_CREDENTIALS)

        self._assert_login_allowed(user)

        # Transparent hash upgrade if cost params changed.
        if password_needs_rehash(user.hashed_password):
            user.hashed_password = hash_password(password)

        await self._reset_failed_login(user)
        tokens = await self._issue_tokens(user)
        await self._audit_auth("login_success", user=user, ip=ip)
        await self.session.commit()
        logger.info("login_success", extra={"user_id": str(user.id)})
        return tokens

    def _assert_login_allowed(self, user: User) -> None:
        if user.status != UserStatus.ACTIVE:
            raise InactiveAccountError("Account is not active")
        # Company users cannot log in if their company is not active.
        if user.company is not None and user.company.status != CompanyStatus.ACTIVE:
            raise InactiveAccountError("Company account is not active")

    async def _register_failed_login(self, user: User) -> None:
        user.failed_login_count += 1
        if user.failed_login_count >= settings.MAX_FAILED_LOGINS:
            user.status = UserStatus.LOCKED
            logger.warning("account_locked", extra={"user_id": str(user.id)})
        await self.session.commit()

    async def _reset_failed_login(self, user: User) -> None:
        user.failed_login_count = 0
        user.last_login_at = datetime.now(timezone.utc)

    # ----- token issuance / rotation ---------------------------------------
    async def _issue_tokens(self, user: User) -> TokenResponse:
        roles = user.role_names
        permissions = sorted(resolve_permissions(roles))
        company_id = str(user.company_id) if user.company_id else None

        access_token, _ = create_access_token(
            user_id=str(user.id),
            company_id=company_id,
            roles=roles,
            permissions=permissions,
        )
        refresh_token, jti, expires_at = create_refresh_token(str(user.id))

        await self.refresh.create(
            user_id=user.id,
            jti=jti,
            token_hash=hash_secret(refresh_token),
            expires_at=expires_at,
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh_tokens(
        self, refresh_token: str, *, ip: str | None = None
    ) -> TokenResponse:
        payload = decode_token(refresh_token, TokenType.REFRESH)
        jti = payload.get("jti")
        record = await self.refresh.get_by_jti(jti) if jti else None

        if record is None or not record.is_active:
            raise AuthenticationError("Invalid or expired refresh token")

        # Token theft detection: stored hash must match presented token.
        if record.token_hash != hash_secret(refresh_token):
            # Possible replay/theft — revoke the whole family.
            await self.refresh.revoke_all_for_user(record.user_id)
            await self.session.commit()
            raise AuthenticationError("Refresh token reuse detected")

        user = await self.users.get_by_id_unscoped(record.user_id)
        if user is None:
            raise AuthenticationError("Invalid refresh token")
        self._assert_login_allowed(user)

        # Rotation: revoke the old token, issue a fresh pair.
        await self.refresh.revoke(record)
        tokens = await self._issue_tokens(user)
        await self._audit_auth("refresh", user=user, ip=ip)
        await self.session.commit()
        return tokens

    # ----- logout -----------------------------------------------------------
    async def logout(self, refresh_token: str, *, ip: str | None = None) -> None:
        try:
            payload = decode_token(refresh_token, TokenType.REFRESH)
        except AuthenticationError:
            return  # already invalid — nothing to do
        record = await self.refresh.get_by_jti(payload.get("jti"))
        if record and record.is_active:
            await self.refresh.revoke(record)
            user = await self.users.get_by_id_unscoped(record.user_id)
            await self._audit_auth("logout", user=user, ip=ip)
            await self.session.commit()

    # ----- password management ---------------------------------------------
    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise ValidationError("Current password is incorrect")
        user.hashed_password = hash_password(new_password)
        # Invalidate all sessions on credential change.
        await self.refresh.revoke_all_for_user(user.id)
        await self.session.commit()

    async def request_password_reset(self, email: str) -> str | None:
        """Returns a reset token. Caller emails it. Returns None if no user —
        but the route always responds identically to prevent enumeration."""
        user = await self.users.get_by_email(email)
        if user is None or user.status != UserStatus.ACTIVE:
            return None
        return create_password_reset_token(str(user.id))

    async def reset_password(self, token: str, new_password: str) -> None:
        payload = decode_token(token, TokenType.PASSWORD_RESET)
        user = await self.users.get_by_id_unscoped(payload.get("sub"))
        if user is None:
            raise NotFoundError("User not found")
        user.hashed_password = hash_password(new_password)
        await self.refresh.revoke_all_for_user(user.id)
        await self.session.commit()

    # ----- email verification -----------------------------------------------
    def request_email_verification(self, user: User) -> str | None:
        """Return a verification token for an unverified user, else None.
        Caller emails it; no DB write here (read-only, mirrors reset request)."""
        if user.is_email_verified:
            return None
        return create_email_verification_token(str(user.id))

    async def verify_email(self, token: str) -> None:
        """Consume a verification token and mark the user's email verified.
        Idempotent: re-verifying an already-verified user is a no-op."""
        payload = decode_token(token, TokenType.EMAIL_VERIFICATION)
        user = await self.users.get_by_id_unscoped(payload.get("sub"))
        if user is None:
            raise NotFoundError("User not found")
        if not user.is_email_verified:
            user.is_email_verified = True
            await self.session.commit()