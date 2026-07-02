"""Development-only database initialization.

Creates all tables directly from the SQLAlchemy models via
``Base.metadata.create_all``. This is a convenience for local development so a
fresh checkout can run without a migration step.

THIS IS NOT A REPLACEMENT FOR ALEMBIC.
- ``create_all`` only creates tables that don't exist; it never alters or drops
  existing tables, so it cannot evolve a schema. Alembic remains the single
  source of truth for schema changes in every shared/staging/production env.
- This module refuses to run when ``ENVIRONMENT == "production"``, and is
  additionally gated behind the opt-in ``DEV_AUTO_CREATE_DB`` flag, so it can
  never fire by accident.

Importing ``app.models`` is required: it registers every model on
``Base.metadata`` so ``create_all`` sees the full schema (the same single
import surface Alembic's ``env.py`` uses).
"""
import logging

from app.core.config import settings
from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine

# Import side effect: registers all tables on Base.metadata. Do not remove.
import app.models  # noqa: F401

logger = logging.getLogger(__name__)


async def init_dev_db() -> None:
    """Create all tables from the ORM models, then optionally seed.

    Safe no-op unless ``DEV_AUTO_CREATE_DB`` is set. Hard-refuses in production.
    """
    if settings.is_production:
        # Belt and suspenders: even if the flag were set, never run in prod.
        logger.warning(
            "init_dev_db called in production environment; skipping."
        )
        return

    if not settings.DEV_AUTO_CREATE_DB:
        return

    logger.warning(
        "DEV_AUTO_CREATE_DB enabled — creating tables from models via "
        "create_all(). This is a development convenience and does NOT replace "
        "Alembic migrations."
    )

    async with engine.begin() as conn:
        # run_sync bridges the sync create_all into the async engine.
        await conn.run_sync(Base.metadata.create_all)

    logger.info(
        "Dev DB tables ensured: %s",
        ", ".join(sorted(Base.metadata.tables.keys())),
    )

    if settings.DEV_AUTO_SEED:
        # Imported lazily so the seed's model imports don't run unless needed.
        from app.db.init_db import run_seed

        async with AsyncSessionLocal() as session:
            await run_seed(
                session,
                super_admin_email=settings.DEV_SEED_ADMIN_EMAIL,
                super_admin_password=settings.DEV_SEED_ADMIN_PASSWORD,
            )
        logger.info("Dev DB seed completed.")
