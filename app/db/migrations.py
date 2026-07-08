from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.core.config import settings

logger = logging.getLogger(__name__)

HEAD_REVISION = "003_admin_dashboard_analytics"

REQUIRED_TABLES = frozenset(
    {
        "products",
        "customers",
        "orders",
        "order_items",
        "upsell_offers",
        "order_upsells",
        "events",
        "pixel_events",
        "webhook_logs",
        "analytics_events",
        "alembic_version",
    }
)


def _alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    url = settings.DATABASE_URL.replace("%", "%%")
    config.set_main_option("sqlalchemy.url", url)
    return config


def run_migrations() -> None:
    logger.info("Running Alembic migrations (upgrade head)")
    command.upgrade(_alembic_config(), "head")
    logger.info("Alembic migrations completed")


def stamp_head() -> None:
    logger.info("Stamping Alembic head at %s", HEAD_REVISION)
    command.stamp(_alembic_config(), HEAD_REVISION)
    logger.info("Alembic stamp completed")


def verify_tables(engine: Engine) -> None:
    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = REQUIRED_TABLES - existing

    if missing:
        raise RuntimeError(
            f"Database schema incomplete. Missing tables: {', '.join(sorted(missing))}"
        )

    logger.info("Verified %d required tables exist", len(REQUIRED_TABLES) - 1)


def initialize_database(engine: Engine) -> None:
    if settings.RUN_MIGRATIONS_ON_STARTUP:
        run_migrations()
    else:
        logger.warning("RUN_MIGRATIONS_ON_STARTUP=false — skipping Alembic upgrade")

    verify_tables(engine)
