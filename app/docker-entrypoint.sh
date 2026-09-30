#!/bin/sh
# A failed migration must prevent the application process from starting.
set -eu

alembic -c /app/alembic.ini upgrade head

# Preserve the existing production Uvicorn module target and worker count.
exec uvicorn main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 2
