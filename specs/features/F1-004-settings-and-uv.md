# F1-004 - Settings and uv

## Goal

Add modern Python packaging, dependency management, and configuration.

## Context

The current repo has no `pyproject.toml` or settings module.

## Requirements

- Add `pyproject.toml` with `uv` workflow.
- Add `.env.example`.
- Add `src/nba_data/config/settings.py`.
- Add unit tests for settings.

## Acceptance Criteria

- `uv sync` works.
- Settings have safe defaults.
- Secrets are not committed.

## Validation

- `uv run pytest tests/unit/test_settings.py`

## Out of Scope

- Production secret management.

## Learning Notes

Configuration belongs in environment variables, not source code.
