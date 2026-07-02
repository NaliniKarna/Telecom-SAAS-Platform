"""Domain exception hierarchy. Services raise these; the API layer maps them to HTTP."""
from typing import Any, Optional


class AppException(Exception):
    """Base for all domain exceptions."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(
        self, message: str = "An error occurred", details: Optional[Any] = None
    ):
        self.message = message
        self.details = details
        super().__init__(message)


class NotFoundError(AppException):
    status_code = 404
    error_code = "not_found"


class ValidationError(AppException):
    status_code = 422
    error_code = "validation_error"


class ConflictError(AppException):
    status_code = 409
    error_code = "conflict"


class AuthenticationError(AppException):
    status_code = 401
    error_code = "authentication_failed"


class PermissionDeniedError(AppException):
    status_code = 403
    error_code = "permission_denied"


class TenantIsolationError(PermissionDeniedError):
    error_code = "tenant_isolation_violation"


class AccountLockedError(AuthenticationError):
    error_code = "account_locked"


class InactiveAccountError(AuthenticationError):
    error_code = "account_inactive"
