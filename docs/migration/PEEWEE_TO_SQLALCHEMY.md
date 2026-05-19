# Peewee to SQLAlchemy Migration

## Current State

The prototype uses Peewee models in `models/` and database helpers in
`db_manager/`. Some legacy code calls `create_tables()` and mixes scraping,
parsing, and database writes.

## Target State

New database code uses:

- SQLAlchemy 2.0 models under `src/nba_data/db/models/`;
- Alembic migrations under `alembic/`;
- PostgreSQL schemas: `raw`, `core`, `stats`, `features`, `ml`, `app`;
- idempotent loaders and explicit constraints.

## Migration Phases

1. Keep legacy Peewee code running as-is.
2. Add SQLAlchemy models for `raw` and `core`.
3. Adapt scraping to cache and pure parsers.
4. Add SQLAlchemy repositories/loaders for core entities.
5. Migrate stats tables after stable parser outputs exist.
6. Remove Peewee only after equivalent SQLAlchemy loaders and migrations exist.

## Rules

- Do not write new Peewee code.
- Do not delete legacy Peewee models in Phase 1.
- Do not use `create_tables()` for new schema work.
- Any new schema change should have an Alembic migration or a documented reason.

## Known Debt

- Legacy `db_manager/db_conf.py` contains hardcoded local credentials.
- Legacy player matching uses `player_name`.
- The current scraper does not consistently extract Basketball Reference player IDs.
- Legacy scrapers directly make HTTP requests and must be adapted in Phase 2.

## Related Phase 2 Plans

- `docs/migration/IDEMPOTENT_LOADER_STRATEGY.md`
- `docs/migration/CORE_TEAM_PLAYER_SEASON_MIGRATION_PLAN.md`
