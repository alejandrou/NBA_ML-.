# Phase 4D - Full Offline Database Preparation / Backfill Readiness

Status: approved
Phase ID: `phase-4d-full-offline-database-preparation`

## Goal

Prepare a real local PostgreSQL database from all currently available cached
Basketball Reference `.html.gz` files before any API phase begins.

The Phase 4D flow is:

```text
existing .html.gz cache -> inventory -> offline processor -> idempotent loader -> PostgreSQL -> quality checks -> readiness docs
```

Phase 4D is offline-only. Full preparation means using the current local cache
as it exists at execution time. It does not mean live scraping, refreshing cache
misses, contacting Basketball Reference, deleting data, or creating new external
raw data.

## Preconditions

- Phase 4C is closed after `F4C-001`, `F4C-002`, and `F4C-003` are reviewed and
  marked `done`.
- The Phase 4 SQLAlchemy migration and idempotent loaders are complete.
- Local PostgreSQL can be started by the owner when a later implementation task
  requires it.
- Any future database preparation run must use only existing cached `.html.gz`
  files.

## Phase Tasks

- `F4D-001`: Cached HTML inventory.
- `F4D-002`: Full offline backfill command.
- `F4D-003`: Data quality validation checks.
- `F4D-004`: API-ready database readiness documentation.

## Allowed Work

- Discover existing cached `.html.gz` files under the configured cache root.
- Infer source URL, cache path, team abbreviation, and season year where
  possible.
- Distinguish valid team-season cache candidates from unsupported, duplicate,
  missing-metadata, invalid, and unreadable files.
- Run Alembic migrations normally during the later backfill workflow.
- Use the existing Phase 4C offline processor.
- Use the existing idempotent loaders.
- Use the existing F4C-003 reporting and quarantine model.
- Load valid cached data into local PostgreSQL during the approved backfill
  task.
- Add repeatable post-load data quality checks.
- Document the final local workflow for future API development.

## Disallowed Work

- Live scraping or Basketball Reference contact.
- Cache-miss refresh or acquisition.
- Deleting raw HTML, database records, local databases, or PostgreSQL volumes.
- Destructive migrations.
- Removing Peewee or legacy code.
- API endpoint implementation.
- Frontend implementation.
- Generated metrics, OVR, ranking, similarity, recommendations, or ML work.
- Branch creation, commit, push, or PR without explicit owner approval.

## Execution Rules

- Inventory work must not write to the database.
- Backfill work must process only valid inventory entries.
- Backfill work must reject or skip invalid processor results before DB writes.
- Database writes must use transaction boundaries so one failed entry does not
  leave partial writes.
- Backfill reruns must be idempotent and must not duplicate core rows.
- Reports must clearly distinguish loaded, skipped, failed, rejected, and
  quarantined entries.
- Tests must use temporary files, local fixtures, fakes, or local database setup
  only. Tests and CI must not contact the network.

## Done Criteria

- Phase 4D tasks are implemented, reviewed, and marked `done`.
- Existing cached `.html.gz` files can be inventoried repeatably.
- Valid cached entries can be loaded into local PostgreSQL through the Phase 4C
  processor and idempotent loaders.
- Rerunning the backfill is safe and does not duplicate core rows.
- Post-load data quality checks produce a clear pass/fail report.
- Documentation explains how future API work can prepare and verify a useful
  local database.
- No live scraping, cache refresh, data deletion, destructive migration,
  API/frontend/OVR/ranking/similarity/recommendations/ML work occurred.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`
