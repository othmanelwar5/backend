#!/bin/sh
set -e

echo "==> Bootstrapping database..."
python -m app.db.bootstrap

# Migrations run only in the bootstrap step above.
export RUN_MIGRATIONS_ON_STARTUP=false

echo "==> Starting Uvicorn..."
exec uvicorn main:app --host 0.0.0.0 --port 80
