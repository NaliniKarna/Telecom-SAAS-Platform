"""Exception handlers: map domain exceptions to a uniform error envelope."""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def _envelope(error_code: str, message: str, details=None, request_id=None):
    return {
        "data": None,
        "meta": {"request_id": request_id},
        "errors": [{"code": error_code, "message": message, "details": details}],
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def _app_exc(request: Request, exc: AppException):
        rid = getattr(request.state, "request_id", None)
        # Expected domain errors log at INFO/WARNING, not ERROR.
        log = logger.warning if exc.status_code < 500 else logger.error
        log("domain_exception", extra={"code": exc.error_code, "request_id": rid})
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.error_code, exc.message, exc.details, rid),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(request: Request, exc: RequestValidationError):
        rid = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "validation_error", "Request validation failed", exc.errors(), rid
            ),
        )

    @app.exception_handler(IntegrityError)
    async def _integrity_exc(request: Request, exc: IntegrityError):
        rid = getattr(request.state, "request_id", None)
        logger.warning("integrity_error", extra={"request_id": rid})
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=_envelope(
                "conflict", "Resource conflict", None, rid
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exc(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", None)
        logger.exception("unhandled_exception", extra={"request_id": rid})
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                "internal_error", "An unexpected error occurred", None, rid
            ),
        )
