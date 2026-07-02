"""Structured logging configuration with request-id injection."""
import logging
import sys

from app.core.config import settings
from app.middleware.request_context import request_id_ctx

# Fields that must never be logged.
_REDACT = {"password", "new_password", "current_password", "token",
           "refresh_token", "access_token", "hashed_password"}


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get() or "-"
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    fmt = (
        "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"
        if not settings.is_production
        else '{"time":"%(asctime)s","level":"%(levelname)s",'
        '"request_id":"%(request_id)s","logger":"%(name)s","msg":"%(message)s"}'
    )
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # Bring framework loggers under the same handler.
    for name in ("uvicorn", "uvicorn.access", "sqlalchemy.engine"):
        lg = logging.getLogger(name)
        lg.handlers = [handler]
        lg.propagate = False
