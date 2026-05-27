# F4C-002 - Connect Offline Processor to Idempotent Loaders

## Goal

Connect validated output from the Phase 4C offline cached HTML processor to the
existing Phase 4 SQLAlchemy idempotent core loaders.

The required boundary is:

```text
validated offline processor entries -> TeamSeasonLoadBatch -> load_team_season_core
```

This task must not load directly from raw HTML. Database writes may happen only
for entries that have already passed offline parse, normalize, and validation.

## Functional Requirements

- Loading starts from `OfflineTeamSeasonProcessingReport` entries, not raw HTML.
- Only entries with `status="validated"` may call DB loaders.
- Processor failures must not call `load_team_season_core(...)`.
- Each validated entry is converted into a `TeamSeasonLoadBatch`.
- Each entry load uses its own transaction savepoint so a failed entry does not
  leave partial database writes.
- Loader orchestration must not call `session.commit()`.
- Caller-owned transaction boundaries remain intact.
- Idempotent reruns of the same validated report must not create duplicate core
  rows.
- Source lineage is retained only in returned report/result objects:
  `source_url`, `cache_path`, `team_abbreviation`, and `season_year`.

## Technical Requirements

- Reuse the existing `load_team_season_core(...)` loader and Phase 4 core
  repositories.
- Do not add SQLAlchemy models, Alembic revisions, DB tables, or source lineage
  columns.
- Do not implement stats table loading or official stat persistence.
- Do not implement F4C-003 reporting or quarantine workflow in this task.
- Do not accept or import `BasketballReferenceClient`, `requests`, `httpx`, or a
  generic network client in the offline loader orchestration module.
- Tests must use local fixtures, synthetic processor reports, SQLite in-memory
  core tables, or skippable local PostgreSQL integration only.

## Acceptance Criteria

- Feature spec exists at
  `specs/features/F4C-002-connect-offline-processor-to-idempotent-loaders.md`.
- Loading starts from validated normalized rows, not raw HTML.
- Processor failure entries do not call DB loaders.
- Validated entries are loaded through existing idempotent core loaders.
- Entry-level loader failures roll back partial DB writes for that entry.
- Loader orchestration does not call `session.commit()`.
- Idempotent reruns create no duplicate core rows.
- Source lineage is preserved at report/result level only.
- No migrations, DB tables, lineage columns, API/frontend/OVR work, or full
  historical load is introduced.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference contact.
- Cache refreshes or cache-miss acquisition.
- Loading directly from raw HTML without validation.
- SQLAlchemy migrations, new DB tables, or destructive DB changes.
- Persisted source lineage columns.
- F4C-003 reporting and quarantine workflow.
- Full historical load.
- API, frontend, generated metrics, OVR, ranking, similarity, or ML work.
