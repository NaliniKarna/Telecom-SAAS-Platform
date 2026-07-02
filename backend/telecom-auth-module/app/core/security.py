"""Security primitives: password hashing, JWT encode/decode, secure token hashing.

Keep crypto in one place. Services depend on these functions, never on the
underlying libraries directly.
"""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt  # type: ignore
from passlib.context import CryptContext

from app.core.config import settings
from app.core.constants import TokenType
from app.core.exceptions import AuthenticationError

# bcrypt with a configurable cost factor.
_pwd_context = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=settings.BCRYPT_ROUNDS
)


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def password_needs_rehash(hashed: str) -> bool:
    """True if the stored hash uses outdated parameters and should be upgraded."""
    return _pwd_context.needs_update(hashed)


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: Optional[dict[str, Any]] = None,
) -> tuple[str, str]:
    """Returns (encoded_jwt, jti). jti is the unique token id for revocation."""
    jti = str(uuid.uuid4())
    now = _now()
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type.value,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)
    encoded = jwt.encode(
        payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded, jti


def create_access_token(
    user_id: str,
    company_id: Optional[str],
    roles: list[str],
    permissions: list[str],
) -> tuple[str, str]:
    return _create_token(
        subject=user_id,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims={
            "company_id": company_id,
            "roles": roles,
            "permissions": permissions,
        },
    )


def create_refresh_token(user_id: str) -> tuple[str, str, datetime]:
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token, jti = _create_token(
        subject=user_id, token_type=TokenType.REFRESH, expires_delta=expires_delta
    )
    return token, jti, _now() + expires_delta


def create_password_reset_token(user_id: str) -> str:
    token, _ = _create_token(
        subject=user_id,
        token_type=TokenType.PASSWORD_RESET,
        expires_delta=timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        ),
    )
    return token


def create_invite_token(user_id: str) -> str:
    """Token for user invites. Uses the PASSWORD_RESET token type (so the same
    'set your password' decode path applies, with no new TokenType), but a much
    longer expiry, since invites are commonly opened hours or days later."""
    token, _ = _create_token(
        subject=user_id,
        token_type=TokenType.PASSWORD_RESET,
        expires_delta=timedelta(
            minutes=settings.INVITE_TOKEN_EXPIRE_MINUTES
        ),
    )
    return token

def create_email_verification_token(user_id: str) -> str:
    token, _ = _create_token(
        subject=user_id,
        token_type=TokenType.EMAIL_VERIFICATION,
        expires_delta=timedelta(
            minutes=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES
        ),
    )
    return token

def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Decode and validate a JWT. Raises AuthenticationError on any problem."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid token")

    if payload.get("type") != expected_type.value:
        raise AuthenticationError("Invalid token type")
    return payload


# --------------------------------------------------------------------------- #
# Opaque secret hashing (refresh tokens stored server-side, API keys)
# --------------------------------------------------------------------------- #
def hash_secret(secret: str) -> str:
    """SHA-256 for high-entropy opaque secrets (not user passwords).

    Used to store refresh tokens and API keys so a DB leak doesn't expose them.
    bcrypt is unnecessary here because the inputs are already high-entropy.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, prefix, hashed_key). Full key shown to user once.

    The random part carries full entropy, so we hash with SHA-256 (fast,
    deterministic) rather than bcrypt — API-key checks must be O(1) indexed
    lookups, and there's no low-entropy secret to slow-hash.
    """
    raw = secrets.token_urlsafe(32)
    full_key = f"tlk_live_{raw}"
    prefix = full_key[:12]
    return full_key, prefix, hash_secret(full_key)


def hash_api_key(full_key: str) -> str:
    """SHA-256 hex of an API key — used for storage and auth-time lookups."""
    return hash_secret(full_key)
