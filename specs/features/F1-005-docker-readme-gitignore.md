# F1-005 - Docker, README, and gitignore

## Goal

Improve local setup documentation and safe file tracking.

## Context

The current Docker Compose has hardcoded credentials and README references `main.py`.

## Requirements

- Update Docker Compose to local Postgres 16 with defaults.
- Update `.gitignore`.
- Rewrite README with realistic setup, validation, and scraper warnings.

## Acceptance Criteria

- Docker Compose does not contain real secrets.
- README points to `scrape_main.py` for the legacy scraper.
- Raw data and `.env` are ignored.

## Validation

- `docker compose config`
- `uv run pytest`

## Out of Scope

- Production deployment.

## Learning Notes

Local development defaults should be easy but not secret-bearing.
