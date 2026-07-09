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


def bootstrap_database() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("Bootstrapping database schema")
    _apply_session_timeouts()

    existing = set(inspect(engine).get_table_names())
    schema_tables = REQUIRED_TABLES - {"alembic_version"}

    if schema_tables.issubset(existing):
        revision = _current_revision()
        if revision == HEAD_REVISION:
            logger.info("Database schema already at head (%s), skipping migration", HEAD_REVISION)
            verify_tables(engine)
            _seed_products()
            return

        if revision:
            logger.info("Database at revision %r; upgrading to %s", revision, HEAD_REVISION)
            run_migrations()
            verify_tables(engine)
            _seed_products()
            return

        logger.info(
            "Schema tables present but Alembic revision is %r; stamping head",
            revision,
        )
        stamp_head()
        verify_tables(engine)
        _seed_products()
        return

    logger.info("Schema incomplete; running Alembic upgrade to head")
    run_migrations()
    verify_tables(engine)
    _seed_products()


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
