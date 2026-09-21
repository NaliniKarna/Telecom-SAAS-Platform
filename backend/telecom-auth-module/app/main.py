"""Application factory: wires middleware, routers, exception handlers."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.db.init_dev_db import init_dev_db
from app.db.sync_default_voice import sync_default_elevenlabs_voice
from app.middleware.request_context import RequestContextMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # Dev-only convenience: create tables from models if explicitly enabled.
    # No-op in production and unless DEV_AUTO_CREATE_DB is set. Not a migration.
    await init_dev_db()
    # Wires ELEVENLABS_DEFAULT_VOICE_ID -> the seeded voice row. Safe in every
    # environment: no-ops unless TTS_PROVIDER=elevenlabs, never raises.
    await sync_default_elevenlabs_voice()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Serve uploaded files (local-disk storage backend). When you migrate to an
    # object store (S3/MinIO/R2), files are served by that provider and this
    # mount becomes unnecessary.
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    app.mount(
        settings.UPLOAD_URL_BASE,
        StaticFiles(directory=settings.UPLOAD_DIR),
        name="uploads",
    )

    @app.get("/health", tags=["System"])
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()