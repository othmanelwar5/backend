"""Pre-start database bootstrap: migrate, stamp, or skip without hanging."""

from __future__ import annotations

import logging
import sys

from sqlalchemy import inspect, text

from app.db.migrations import (
    HEAD_REVISION,
    REQUIRED_TABLES,
    run_migrations,
    stamp_head,
    verify_tables,
)
from app.db.session import engine

logger = logging.getLogger(__name__)

# Products that must always exist in the database for order creation to work.
REQUIRED_PRODUCTS = [
    ("d3-k2-gummies",          "MZN-D3K2-8417", "حلوى فيتامين D3 و K2",        "D3+K2 Gummies",          199, 279, 349),
    ("sleep-tea",              "MZN-SLP-2935",  "شاي الأشواغاندا والمغنيسيوم", "Sleep Tea",              199, 279, 349),
    ("probiotic-fiber-gummies","MZN-PRB-6102",  "حلوى البروبيوتيك والألياف",   "Probiotic Fiber Gummies",199, 279, 349),
]


def _apply_session_timeouts() -> None:
    with engine.connect() as connection:
        connection.execute(text("SET lock_timeout = '30s'"))
        connection.execute(text("SET statement_timeout = '120s'"))


def _current_revision() -> str | None:
    inspector = inspect(engine)
    if "alembic_version" not in inspector.get_table_names():
        return None

    with engine.connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()


REPAIR_STATEMENTS = [
    # Needed for gen_random_uuid() on PostgreSQL < 13; the role may lack the
    # privilege, which is fine because each statement is isolated.
    'CREATE EXTENSION IF NOT EXISTS "pgcrypto"',
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS sku VARCHAR(30)",
    "UPDATE products SET sku = slug WHERE sku IS NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS ix_products_sku ON products (sku)",
    """
    CREATE TABLE IF NOT EXISTS analytics_events (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        event_name VARCHAR(60) NOT NULL,
        session_id VARCHAR(120) NOT NULL,
        occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        path TEXT,
        url TEXT,
        referrer TEXT,
        user_agent TEXT,
        product_slug VARCHAR(100),
        order_number VARCHAR(30),
        properties JSONB NOT NULL DEFAULT '{}',
        ip_address INET,
        country_code VARCHAR(2),
        is_vpn BOOLEAN NOT NULL DEFAULT false,
        is_proxy BOOLEAN NOT NULL DEFAULT false,
        is_tor BOOLEAN NOT NULL DEFAULT false,
        is_hosting BOOLEAN NOT NULL DEFAULT false,
        is_bot BOOLEAN NOT NULL DEFAULT false,
        risk_score FLOAT NOT NULL DEFAULT 0.0,
        vpn_provider VARCHAR(80),
        vpn_provider_payload JSONB NOT NULL DEFAULT '{}',
        maxmind_payload JSONB NOT NULL DEFAULT '{}',
        valid_for_metrics BOOLEAN NOT NULL DEFAULT false,
        rejected_reason VARCHAR(200),
        bot_score INTEGER NOT NULL DEFAULT 0
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_analytics_events_occurred_at ON analytics_events (occurred_at)",
    "CREATE INDEX IF NOT EXISTS ix_analytics_events_session ON analytics_events (session_id)",
    "CREATE INDEX IF NOT EXISTS ix_analytics_events_product ON analytics_events (product_slug)",
    (
        "CREATE INDEX IF NOT EXISTS ix_analytics_events_valid_name_date "
        "ON analytics_events (valid_for_metrics, event_name, occurred_at)"
    ),
]


def _repair_schema() -> None:
    """Align the live schema with the ORM models, independently of Alembic.

    Alembic runs every revision inside a single transaction, so one failing
    revision rolls back the others and leaves the database on an old revision
    forever. Orders then crash on `SELECT products.sku`. Each statement below is
    idempotent and committed on its own so a single failure cannot undo the rest.
    """
    for statement in REPAIR_STATEMENTS:
        try:
            with engine.begin() as conn:
                conn.execute(text(statement))
        except Exception:
            logger.exception("Schema repair statement failed: %s", statement.strip().split("\n")[0])


def _seed_products() -> None:
    """Ensure the three core products exist using upsert so it is safe to run repeatedly."""
    try:
        with engine.begin() as conn:
            for slug, sku, name_ar, name_en, p1, p2, p3 in REQUIRED_PRODUCTS:
                conn.execute(
                    text(
                        """
                        INSERT INTO products (slug, sku, name_ar, name_en, price_1, price_2, price_3, active)
                        VALUES (:slug, :sku, :name_ar, :name_en, :p1, :p2, :p3, true)
                        ON CONFLICT (slug) DO UPDATE
                            SET sku      = EXCLUDED.sku,
                                name_ar  = EXCLUDED.name_ar,
                                name_en  = EXCLUDED.name_en,
                                price_1  = EXCLUDED.price_1,
                                price_2  = EXCLUDED.price_2,
                                price_3  = EXCLUDED.price_3,
                                active   = true
                        """
                    ),
                    {"slug": slug, "sku": sku, "name_ar": name_ar, "name_en": name_en,
                     "p1": p1, "p2": p2, "p3": p3},
                )
        logger.info("Product seed completed (%d products upserted)", len(REQUIRED_PRODUCTS))
    except Exception:
        logger.exception("Product seed failed — orders may not work until products exist")


def _run_alembic() -> None:
    existing = set(inspect(engine).get_table_names())
    schema_tables = REQUIRED_TABLES - {"alembic_version"}

    if not schema_tables.issubset(existing):
        logger.info("Schema incomplete; running Alembic upgrade to head")
        run_migrations()
        return

    revision = _current_revision()
    if revision == HEAD_REVISION:
        logger.info("Database schema already at head (%s), skipping migration", HEAD_REVISION)
        return

    if revision:
        logger.info("Database at revision %r; upgrading to %s", revision, HEAD_REVISION)
        run_migrations()
        return

    logger.info("Schema tables present but no Alembic revision; stamping head")
    stamp_head()


def bootstrap_database() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Bootstrapping database schema")
    _apply_session_timeouts()

    try:
        _run_alembic()
    except Exception:
        logger.exception("Alembic upgrade failed — falling back to direct schema repair")

    # Always runs, even when Alembic is stuck on an old revision.
    _repair_schema()
    _seed_products()

    try:
        verify_tables(engine)
    except Exception:
        logger.exception("Table verification failed after schema repair")


def main() -> int:
    try:
        bootstrap_database()
    except Exception:
        logger.exception("Database bootstrap failed")
        return 1

    logger.info("Database bootstrap completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
