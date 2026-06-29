#!/bin/sh
set -eu

# EasyPanel injects PORT at runtime. Default to 80 to match service docs.
PORT="${PORT:-80}"

echo "==> Starting Uvicorn on 0.0.0.0:${PORT}"
exec uvicorn main:app --host 0.0.0.0 --port "${PORT}"
