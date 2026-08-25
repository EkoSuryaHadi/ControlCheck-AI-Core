#!/bin/bash
set -euo pipefail

echo "=================================================="
echo "ControlCheck AI — Production Container Entrypoint"
echo "=================================================="

# 1. Wait for Database if configured
if [ -n "${CONTROLCHECK_DATABASE_URL:-}" ]; then
    echo "Waiting for database to be ready..."
    max_retries=30
    counter=0
    until python -c "
import os, sys
from sqlalchemy import create_engine, text
url = os.environ.get('CONTROLCHECK_DATABASE_URL')
try:
    engine = create_engine(url)
    with engine.connect() as conn:
        conn.execute(text('SELECT 1'))
    sys.exit(0)
except Exception as e:
    sys.exit(1)
" 2>/dev/null; do
        counter=$((counter + 1))
        if [ "$counter" -gt "$max_retries" ]; then
            echo "ERROR: Database connection timed out after $max_retries attempts."
            exit 1
        fi
        echo "Database unavailable, waiting 2 seconds (attempt $counter/$max_retries)..."
        sleep 2
    done
    echo "Database is reachable."

    # 2. Run Alembic Migrations
    echo "Applying latest database migrations (alembic upgrade head)..."
    alembic upgrade head
    echo "Database migrations applied successfully."
fi

echo "Starting ControlCheck AI server on port ${PORT:-8000}..."
if [ "$#" -eq 0 ] || [ "$1" = "uvicorn" ]; then
    exec uvicorn controlcheck.asgi:app --app-dir src --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}"
else
    exec "$@"
fi
