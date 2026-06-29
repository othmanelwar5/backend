#!/bin/sh
set -e

echo "==> Running database migrations..."
timeout "${MIGRATION_TIMEOUT_SECONDS:-60}" alembic upgrade head

# Migrations are a pre-start step. The FastAPI process should only verify the
# schema so app startup cannot block behind Alembic and keep the proxy at 502.
export RUN_MIGRATIONS_ON_STARTUP=false

echo "==> Starting Uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 80
