#!/bin/sh
set -e

echo "==> Bootstrapping database..."
python -m app.db.bootstrap

# Migrations run only in the bootstrap step above.
export RUN_MIGRATIONS_ON_STARTUP=false

PORT="${PORT:-80}"
echo "==> Starting Uvicorn on port ${PORT}..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT}"
