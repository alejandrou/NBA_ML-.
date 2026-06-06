# Current Work

Status: phase_4e_f4e_001_needs_review

## Active Task

- `F4E-001`: Official wide stats schema plan.
- Status: `needs_review`.
- This checkpoint is documentation-only.

## Current Phase

- Phase ID: `phase-4e-official-wide-stats-persistence`.
- Phase status: `in_progress`.
- Phase 4E remains pre-API.

## Phase 4D Baseline

Phase 4D is closed as `core relational database readiness`. The owner confirmed
these PostgreSQL counts:

```text
core.seasons                26
core.teams                  37
core.team_aliases           775
core.team_seasons           775
core.players                2551
core.player_seasons         12676
core.player_team_seasons    14344
```

The Phase 4D closure source is `docs/validation/OFFLINE_DATABASE_PREPARATION.md`
and the final closure notes in `progress/review.md`. The requested
`docs/validation/PHASE_4D_CORE_DATABASE_CLOSURE.md` file is absent.

## Latest Checkpoint

- Activated Phase 4E as the current phase after owner approval.
- Finalized `docs/architecture/OFFICIAL_STATS_SCHEMA.md` as the reviewed schema
  contract for official Basketball Reference wide stats persistence.
- Documented all 17 additive `stats` tables:
  `stats.player_team_season_roster`, 8 team-stint stats tables, and 8
  aggregate player-season stats tables.
- Documented FK grains, unique constraints, lineage columns, nullable stat
  columns, SQL type recommendations, and `normalized key -> DB column`
  mappings for all nine supported source families.
- Documented `TOT` routing: roster never loads `TOT`, real-team stats use
  `core.player_team_seasons.id`, and aggregate `TOT` stats use
  `core.player_seasons.id`.
- Updated the F4E-001 and F4E-002 specs so the next task can implement models
  and migration without redesigning the schema.
- Updated the legacy schema review to preserve useful concepts while rejecting
  legacy identity and typing defects.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 158 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 158
  passed, 1 skipped, and 6 Peewee deprecation warnings.

## Guardrails Observed

- No SQLAlchemy stats models were added.
- No Alembic migration was created.
- No repositories, loaders, backfill commands, API endpoints, frontend pages,
  generated metrics, OVR, rankings, similarity, recommendations, or ML work
  were introduced.
- No database writes, live scraping, Basketball Reference contact, cache
  refresh, branch, commit, push, or PR occurred.

## Next Safe Action

Review `F4E-001`. After approval, promote `F4E-002` to implement the reviewed
`stats` SQLAlchemy models and Alembic migration.
