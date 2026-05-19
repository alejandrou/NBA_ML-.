#!/usr/bin/env bash
set -euo pipefail

echo "Running harness init checks..."

required_files=(
  "AGENTS.md"
  "docs/ai/WORKFLOW_PROTOCOL.md"
  "docs/roadmap/PHASE_GOVERNANCE.md"
  "docs/roadmap/CURRENT_PHASE.md"
  "tasks/feature-list.json"
  "progress/current.md"
  "progress/history.md"
)

for file in "${required_files[@]}"; do
  if [ ! -f "$file" ]; then
    echo "Missing required file: $file"
    exit 1
  fi
done

current_phase_id="$(python - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("tasks/feature-list.json").read_text(encoding="utf-8"))
phase_id = data.get("current_phase_id")
if not phase_id:
    raise SystemExit("tasks/feature-list.json missing current_phase_id")
print(phase_id)
PY
)"

current_phase_spec="specs/phases/${current_phase_id}.md"

if [ ! -f "$current_phase_spec" ]; then
  echo "Missing current phase spec: $current_phase_spec"
  exit 1
fi

required_files+=("$current_phase_spec")

future_phase_specs=(
  "specs/phases/phase-1-foundations.md"
  "specs/phases/phase-2-scraper-cache-integration.md"
  "specs/phases/phase-3-parser-normalization.md"
  "specs/phases/phase-4-sqlalchemy-migration.md"
  "specs/phases/phase-5-api.md"
  "specs/phases/phase-6-frontend.md"
  "specs/phases/phase-7-features-ovr.md"
)

for spec in "${future_phase_specs[@]}"; do
  if [ "$spec" != "$current_phase_spec" ] && [ ! -f "$spec" ]; then
    echo "Warning: future phase spec is missing: $spec"
  fi
done

if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  ignored_files=()
  untracked_required_files=()

  for file in "${required_files[@]}"; do
    if git check-ignore -q -- "$file"; then
      ignored_files+=("$file")
    fi

    if ! git ls-files --error-unmatch -- "$file" >/dev/null 2>&1; then
      untracked_required_files+=("$file")
    fi
  done

  if [ "${#ignored_files[@]}" -gt 0 ]; then
    echo "Required files are ignored by Git:"
    printf '  %s\n' "${ignored_files[@]}"
    exit 1
  fi

  if [ "${#untracked_required_files[@]}" -gt 0 ]; then
    echo "Required files are not tracked by Git:"
    printf '  %s\n' "${untracked_required_files[@]}"
    exit 1
  fi
fi

if [ -f "pyproject.toml" ]; then
  if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found. Install uv before running project validation."
    exit 1
  fi
fi

echo "Harness init checks passed."
