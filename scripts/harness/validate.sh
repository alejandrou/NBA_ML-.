#!/usr/bin/env bash
set -euo pipefail

echo "Running harness validation..."

bash scripts/harness/init.sh

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install uv and run 'uv sync'."
  exit 1
fi

uv run ruff check .
uv run pytest

echo "Harness validation passed."
