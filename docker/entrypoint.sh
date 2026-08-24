#!/bin/sh
set -eu

: "${PORT:=8000}"

alembic upgrade head
exec uvicorn controlcheck.api:app --app-dir src --host 0.0.0.0 --port "$PORT"
