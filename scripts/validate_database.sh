#!/usr/bin/env bash
# Starts local PostgreSQL and delegates validation to the disposable database
# lane. It never writes to the configured database.
# Local development only — never point this at a shared or production database.
set -euo pipefail

echo "Running database validation..."

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install uv and run 'uv sync'."
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found. Install Docker or start PostgreSQL manually."
  exit 1
fi

POSTGRES_USER="${POSTGRES_USER:-nba}"
POSTGRES_DB="${POSTGRES_DB:-nba}"

docker compose up -d postgres

for attempt in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
    break
  fi

  if [ "$attempt" -eq 30 ]; then
    echo "PostgreSQL did not become ready in time."
    exit 1
  fi

  sleep 1
done

exec uv run python scripts/validate_postgres_local.py
