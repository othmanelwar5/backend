#!/bin/sh
set -e

if [ "$RUN_MIGRATIONS_ON_STARTUP" = "true" ] || [ "$RUN_MIGRATIONS_ON_STARTUP" = "True" ]; then
    echo "==> Running Alembic migrations..."
    alembic upgrade head
    echo "==> Migrations complete."
else
    echo "==> Skipping migrations (RUN_MIGRATIONS_ON_STARTUP is not true)."
fi

echo "==> Starting Uvicorn on port 80..."
exec uvicorn main:app --host 0.0.0.0 --port 80
