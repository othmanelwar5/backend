#!/bin/sh

PORT="${PORT:-80}"
BOOTSTRAP_TIMEOUT="${BOOTSTRAP_TIMEOUT_SECONDS:-45}"

echo "==> Bootstrapping database (max ${BOOTSTRAP_TIMEOUT}s)..."
if timeout "${BOOTSTRAP_TIMEOUT}" python -m app.db.bootstrap; then
  echo "==> Database bootstrap succeeded"
else
  echo "WARNING: database bootstrap failed or timed out; starting API anyway"
fi

export RUN_MIGRATIONS_ON_STARTUP=false

echo "==> Starting Uvicorn on port ${PORT}..."
exec uvicorn main:app --host 0.0.0.0 --port "${PORT}"
