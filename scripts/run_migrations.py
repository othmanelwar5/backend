#!/usr/bin/env python3
"""Run Alembic migrations and print verification proof."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import inspect, text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.migrations import REQUIRED_TABLES, initialize_database  # noqa: E402
from app.db.session import engine  # noqa: E402


def main() -> int:
    print(f"DATABASE_URL host/db: ...@{settings.DATABASE_URL.rsplit('@', 1)[-1]}")
    initialize_database(engine)

    with engine.connect() as conn:
        db_name = conn.execute(text("SELECT current_database()")).scalar()
        schema = conn.execute(text("SELECT current_schema()")).scalar()
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        tables = sorted(inspect(engine).get_table_names())

    print(f"\nConnected database : {db_name}")
    print(f"Schema             : {schema}")
    print(f"Alembic revision   : {version}")
    print(f"\nTables ({len(tables)}):")
    for name in tables:
        print(f"  - {name}")

    missing = REQUIRED_TABLES - set(tables)
    if missing:
        print(f"\nERROR: missing tables: {', '.join(sorted(missing))}")
        return 1

    print("\nOK: all required ecommerce tables exist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
