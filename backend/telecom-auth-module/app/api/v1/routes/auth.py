"""Authentication endpoints."""
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Request,
    UploadFile,
    status,
)

from app.api.v1.deps import CurrentUser, get_auth_service, get_profile_service
from app.core.config import settings
from app.core.exceptions import ValidationError
from app.core.rbac import resolve_permissions
from app.core.storage import get_storage
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    VerifyEmailRequest,
    MeResponse,
    ProfileUpdate,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/auth", tags=["Authentication"])

AuthDep = Annotated[AuthService, Depends(get_auth_service)]
ProfileDep = Annotated[ProfileService, Depends(get_profile_service)]

_ALLOWED_AVATAR_TYPES = {
    "image/png", "image/jpeg", "image/jpg", "image/webp",
}


def _client_ip(request: Request) -> str | None:
    """Best source IP for audit. Prefers the left-most X-Forwarded-For hop when
    present (set by a trusted reverse proxy / load balancer), else the socket
    peer. NOTE: X-Forwarded-For is client-supplied and therefore spoofable
    unless your proxy overwrites it — confirm your edge strips/sets this header
    before relying on it for security decisions."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, service: AuthDep, request: Request
) -> TokenResponse:
    return await service.login(
        payload.email, payload.password, ip=_client_ip(request)
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest, service: AuthDep, request: Request
) -> TokenResponse:
    return await service.refresh_tokens(
        payload.refresh_token, ip=_client_ip(request)
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest, service: AuthDep, request: Request
) -> None:
    await service.logout(payload.refresh_token, ip=_client_ip(request))


@router.get("/me", response_model=MeResponse)
async def me(current_user: CurrentUser) -> MeResponse:
    return _me_response(current_user)


@router.patch("/me", response_model=MeResponse)
async def update_me(
    payload: ProfileUpdate,
    current_user: CurrentUser,
    service: ProfileDep,
    request: Request,
) -> MeResponse:
    user = await service.update_profile(
        current_user, payload, ip=_client_ip(request)
    )
    return _me_response(user)


@router.post("/me/avatar", response_model=MeResponse)
async def upload_avatar(
    current_user: CurrentUser,
    service: ProfileDep,
    request: Request,
    file: UploadFile = File(...),
) -> MeResponse:
    if file.content_type not in _ALLOWED_AVATAR_TYPES:
        raise ValidationError("Avatar must be a PNG, JPEG, or WebP image")
    data = await file.read()
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"Avatar exceeds the {settings.MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit"
        )
    url = get_storage().save(
        data=data,
        filename=file.filename or "avatar",
        content_type=file.content_type or "application/octet-stream",
        prefix=f"avatars/{current_user.id}",
    )
    user = await service.set_avatar(current_user, url, ip=_client_ip(request))
    return _me_response(user)


def _me_response(user) -> MeResponse:
    roles = user.role_names
    return MeResponse(
        id=user.id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        company_id=user.company_id,
        roles=roles,
        permissions=sorted(resolve_permissions(roles)),
        is_email_verified=user.is_email_verified,
        last_login_at=user.last_login_at,
        avatar_url=user.avatar_url,
    )


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: CurrentUser,
    service: AuthDep,
) -> None:
    await service.change_password(
        current_user, payload.current_password, payload.new_password
    )


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    payload: ForgotPasswordRequest,
    service: AuthDep,
    background_tasks: BackgroundTasks,
) -> dict:
    # Always return the same response regardless of whether the email exists.
    token = await service.request_password_reset(payload.email)
    if token:
        # Send out-of-band so the response stays uniform and fast.
        background_tasks.add_task(
            EmailService().send_password_reset, payload.email, token
        )
    return {
        "message": "If an account exists for that email, a reset link has been sent."
    }


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(payload: ResetPasswordRequest, service: AuthDep) -> None:
    await service.reset_password(payload.token, payload.new_password)

@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email(payload: VerifyEmailRequest, service: AuthDep) -> None:
    await service.verify_email(payload.token)


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
async def resend_verification(
    current_user: CurrentUser,
    service: AuthDep,
    background_tasks: BackgroundTasks,
) -> dict:
    # Authenticated: re-send a verification link for the current user.
    token = service.request_email_verification(current_user)
    if token:
        background_tasks.add_task(
            EmailService().send_email_verification, current_user.email, token
        )
    return {"message": "If your email is unverified, a link has been sent."}