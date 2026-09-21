"""Exception handlers: map domain exceptions to a uniform error envelope.

CORS note: FastAPI wires a handler registered for the bare `Exception` class
into Starlette's ServerErrorMiddleware, which is the true outermost ASGI
layer — above even CORSMiddleware (confirmed directly against Starlette
0.41.3 source: ServerErrorMiddleware.__call__ sends its response via the raw
transport `send` it received before any user-added middleware, including
CORSMiddleware, ever wrapped it). That means a response built by the
catch-all handler below NEVER passes through CORSMiddleware's header
injection — the browser sees a response with no Access-Control-Allow-Origin
header and reports it as "blocked by CORS policy", even though the real
cause is whatever server-side exception the traceback (logged right here)
actually shows. This bit every route in the API, not anything specific to
one feature — it's a structural fact about how Starlette wires bare-`Exception`
handlers, not a bug in any single endpoint.

The fix: every handler here attaches CORS headers itself, mirroring exactly
what CORSMiddleware computes for a normal ("simple", non-preflight) response
(see CORSMiddleware.send()/is_allowed_origin() in starlette/middleware/cors.py)
so the browser gets a correct, readable error response no matter which
middleware layer ends up actually sending it.
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def _cors_headers(request: Request) -> dict:
    """Mirrors CORSMiddleware's simple-response logic for a single request,
    since ServerErrorMiddleware bypasses CORSMiddleware entirely for
    bare-Exception handlers (see module docstring). Returns {} when the
    request has no Origin header or the origin isn't in settings.CORS_ORIGINS
    — i.e. exactly when the real CORSMiddleware would also add nothing.
    """
    origin = request.headers.get("origin")
    if not origin or origin not in settings.CORS_ORIGINS:
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    }


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
            headers=_cors_headers(request),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exc(request: Request, exc: RequestValidationError):
        rid = getattr(request.state, "request_id", None)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                "validation_error", "Request validation failed", exc.errors(), rid
            ),
            headers=_cors_headers(request),
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
            headers=_cors_headers(request),
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
            headers=_cors_headers(request),
        )