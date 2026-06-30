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
            return

        if revision:
            logger.info("Database at revision %r; upgrading to %s", revision, HEAD_REVISION)
            run_migrations()
            verify_tables(engine)
            return

        logger.info(
            "Schema tables present but Alembic revision is %r; stamping head",
            revision,
        )
        stamp_head()
        verify_tables(engine)
        return

    logger.info("Schema incomplete; running Alembic upgrade to head")
    run_migrations()
    verify_tables(engine)


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
