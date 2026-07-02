"""Authentication request/response schemas."""
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.config import settings


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # access token lifetime in seconds


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str


class LogoutRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str


class _PasswordMixin(BaseModel):
    @staticmethod
    def _validate_strength(v: str) -> str:
        if len(v) < settings.PASSWORD_MIN_LENGTH:
            raise ValueError(
                f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters"
            )
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain an uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain a lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain a digit")
        return v


class ChangePasswordRequest(_PasswordMixin):
    model_config = ConfigDict(extra="forbid")
    current_password: str
    new_password: str

    def model_post_init(self, __ctx) -> None:
        self._validate_strength(self.new_password)


class ForgotPasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class ResetPasswordRequest(_PasswordMixin):
    model_config = ConfigDict(extra="forbid")
    token: str
    new_password: str

    def model_post_init(self, __ctx) -> None:
        self._validate_strength(self.new_password)

class VerifyEmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str

class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    first_name: str | None
    last_name: str | None
    company_id: uuid.UUID | None
    roles: list[str]
    permissions: list[str]
    last_login_at: datetime | None = None
    is_email_verified: bool = False
    avatar_url: str | None = None


class ProfileUpdate(BaseModel):
    """Self-service profile edit. Email is immutable (it's the login identity);
    roles/status are never self-editable."""
    model_config = ConfigDict(extra="forbid")
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
