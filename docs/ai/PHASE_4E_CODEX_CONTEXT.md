# Phase 4E Codex Context

## Phase

`phase-4e-official-wide-stats-persistence` - Phase 4E Official Basketball
Reference Wide Stats Persistence

## Goal

Persist official Basketball Reference player statistics in typed relational
`stats` tables from cached team-season HTML. Keep identity and relationships in
`core` and future generated metrics in `features`.

Phase 4E is pre-API. `F4E-005` is closed by explicit owner approval,
`F4E-006` has `changes_requested`, and `F4E-007` is the next ready task.

## Current task state

- `F4E-001`: done
- `F4E-002`: done
- `F4E-003`: done
- `F4E-004`: done
- `F4E-005`: done
- `F4E-006`: changes_requested
- `F4E-007`: ready
- `F4E-008`: pending
- `F4E-009`: pending

Source of truth:

- `tasks/feature-list.json`
- `docs/roadmap/CURRENT_PHASE.md`
- `docs/roadmap/TASKS.md`
- `progress/current.md`
- `progress/review.md`
- `docs/ai/REPO_MAP.md`
- `docs/ai/ARCHITECTURE_INVARIANTS.md`
- `docs/ai/tasks/README.md`

## Architecture decisions

- `core` owns identity and relationships.
- `stats` owns official scraped stats.
- `features` is reserved for generated metrics.
- Team-season pages populate `stats.player_team_season_*`.
- Player pages populate `stats.player_season_*`.
- Real team stint stats FK to `core.player_team_seasons.id`.
- Full player-season stats FK to `core.player_seasons.id`.
- `2TM`, `3TM`, and `4TM` are player-page `source_team_code` metadata, not
  teams.
- `TOT` is not a real team and is not the source for supported Phase 4E season
  stats.
- `stats.player_team_season_roster` is team-stint only.
- Official stat columns are typed and nullable by default.
- `player_name` is not a stable key.
- Regular-season and postseason stats are separate table families.

## In scope

- Documentation and task planning for player-page regular-season aggregate
  stats, postseason stats, and final validation closure.
- Phase documentation, progress updates, and validation notes for 4E.

## Out of scope

- Live scraping.
- Cache refresh or acquisition.
- API or frontend work.
- Generated metrics, OVR, ranking, similarity, recommendations, or ML.
- Destructive database operations or Peewee removal.

## Key files

- `docs/roadmap/CURRENT_PHASE.md`
- `docs/roadmap/TASKS.md`
- `docs/architecture/OFFICIAL_STATS_SCHEMA.md`
- `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md`
- `docs/migration/LEGACY_STATS_SCHEMA_REVIEW.md`
- `src/nba_data/db/models/stats.py`
- `alembic/versions/0003_stats_wide_tables.py`
- `src/nba_data/db/repositories/stats.py`
- `src/nba_data/scraping/loaders/team_season_stats.py`
- `src/nba_data/scraping/offline_processor.py`
- `specs/phases/phase-4e-official-wide-stats-persistence.md`
- `specs/features/F4E-005-offline-stats-backfill-command.md`
- `specs/features/F4E-006-official-stats-validation-checks.md`
- `specs/features/F4E-007-player-page-regular-season-aggregate-stats-backfill.md`
- `specs/features/F4E-008-postseason-stats-schema-and-player-page-backfill.md`
- `specs/features/F4E-009-official-stats-final-validation-and-db-closure.md`
- `src/nba_data/validation/official_stats.py`
- `src/nba_data/cli/main.py`
- `tests/unit/test_official_stats_validation.py`

## Key specs

- `specs/phases/phase-4e-official-wide-stats-persistence.md`
- `specs/features/F4E-005-offline-stats-backfill-command.md`
- `specs/features/F4E-006-official-stats-validation-checks.md`

## Validation commands

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `uv run alembic upgrade head`
- `uv run alembic check`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Branch and commit notes

- Do not create a branch, commit, push, or open a PR unless explicitly
  requested.
- Use one commit per task or phase unit when a commit is requested.

## Next phase gate

`F4E-007` is the next recommended task. Phase 4E closure requires the later
`F4E-009` final validation/database closure task. Phase 5 stays pending until
Phase 4E is complete.

## Update policy

Update this file when:

- the phase starts;
- a major decision changes;
- task states change significantly;
- the next phase gate changes.

Keep this file short, factual, and phase-scoped.
Do not duplicate full specs.
