#!/usr/bin/env bash
set -euo pipefail

echo "Running harness close checks..."

bash scripts/harness/validate.sh

required_files=(
  "progress/current.md"
  "progress/history.md"
  "progress/review.md"
  "progress/blockers.md"
  "docs/roadmap/CHANGELOG_LEARNING.md"
  "docs/roadmap/TASKS.md"
)

for file in "${required_files[@]}"; do
  if [ ! -f "$file" ]; then
    echo "Missing required close file: $file"
    exit 1
  fi
done

if command -v git >/dev/null 2>&1; then
  staged_files="$(git diff --cached --name-only || true)"
  if printf "%s\n" "$staged_files" | grep -E '(^|/)\.env$|^data/raw/' >/dev/null 2>&1; then
    echo "Unsafe staged file detected: .env or data/raw"
    exit 1
  fi
fi

echo "Harness close checks passed."
