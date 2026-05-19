# Phase 1 - Foundations

Status: done
Phase ID: `phase-1-foundations`

## Goal

Create the project harness, local development foundation, responsible scraping
guardrails, cache, parser pattern, SQLAlchemy foundation, tests, and CI.

## Allowed Work

- Project instructions, roles, skills, and workflow documentation.
- Feature list, progress memory, and feature specs.
- Local settings, dependency management, Docker Compose, README, and gitignore.
- Harness scripts, central rate-limited client, HTML cache, parser pattern,
  SQLAlchemy/Alembic foundation, tests, and CI.

## Forbidden Without Owner Approval

- Live scraping.
- Historical scraping.
- Full database migration.
- API implementation.
- Frontend implementation.
- OVR, ranking, similarity, or ML feature implementation.

## Sensitive Gates

- Contacting Basketball Reference.
- Deleting data or local databases.
- Removing Peewee or legacy code.
- Creating branches, opening pull requests, or pushing commits.

## Initial Ready Tasks

None. This phase is done.

## Done Criteria

- F1-001 through F1-011 are `done`.
- Ruff, Pytest, and harness validation pass.
- No live scraping was run.
- Phase 1 review is closed.

## Default Validations

- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Next Phase Recommendation

Proceed to `phase-2-scraper-cache-integration` as a proposed phase.
