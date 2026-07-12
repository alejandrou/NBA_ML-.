#!/usr/bin/env bash
set -euo pipefail

echo "Running harness init checks..."

required_files=("AGENTS.md" "tasks/CURRENT.md" "docs/roadmap/ROADMAP.md" "scripts/harness/validate_workflow.py")

for file in "${required_files[@]}"; do
  if [ ! -f "$file" ]; then
    echo "Missing required file: $file"
    exit 1
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
