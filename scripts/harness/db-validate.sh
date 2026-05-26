#!/usr/bin/env bash
set -euo pipefail

echo "Running database validation..."

bash scripts/harness/init.sh

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

uv run alembic upgrade head
uv run alembic check
uv run pytest tests/integration/test_team_season_loader_postgres.py

echo "Database validation passed."
