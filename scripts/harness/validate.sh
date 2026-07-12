#!/usr/bin/env bash
set -euo pipefail

echo "Running harness validation..."

python scripts/harness/validate_workflow.py

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found. Install uv and run 'uv sync'."
  exit 1
fi

uv run ruff check .
uv run pytest
git diff --check

echo "Harness validation passed."
