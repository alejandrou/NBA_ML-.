# Core Team Player Season Migration Plan

## Purpose

This document prepared the reviewed migration path for core team, player, and
season entities. Phase 4 task `F4-001` now implements the first additive
SQLAlchemy/Alembic slice while preserving legacy Peewee coexistence.

## Current Foundation

The SQLAlchemy foundation already includes:

- `core.seasons` with a unique `(league, season_year)` constraint;
- `core.teams` with Basketball Reference team identifier fields and an index on
  `basketball_reference_team_id`;
- `core.team_aliases` for abbreviation/name history across season ranges;
- `core.players` with a unique `basketball_reference_player_id` constraint;
- Alembic as the migration mechanism for new schema work.

`F4-001` adds:

- a unique Basketball Reference team identifier constraint on `core.teams`;
- `TOT` check constraints for real team identifiers and aliases;
- `core.team_seasons` for real team-season membership;
- `core.player_seasons` for player-season identity;
- `core.player_team_seasons` for roster stint membership without stats.

`F4-002` adds:

- SQLAlchemy repository methods for idempotent core identity records;
- a team-season core loader for already-normalized rows;
- validation-before-write behavior and caller-owned transaction boundaries;
- SQLite unit coverage plus a PostgreSQL smoke test through the migrated schema.

Legacy Peewee models remain under `models/`, and legacy database operations
remain under `db_manager/`. They must continue to coexist until equivalent
SQLAlchemy loaders and migrations are reviewed in a later phase.

## Target Modeling Rules

- `season_year = 2024` represents the 2023-24 NBA season.
- `player_name` is not a stable primary key; use
  `basketball_reference_player_id` when available.
- `TOT` is not a team and should not be inserted as a team alias.
- Team aliases preserve historical abbreviations and names without overwriting
  the canonical team row.
- Official scraped stats remain separate from generated metrics.

## Migration Sequence

1. Keep existing Peewee tables and legacy write paths untouched.
2. Expand parser and normalizer coverage until team-season rows have stable
   identifiers and validation checks.
3. Review any needed SQLAlchemy model changes for `core` entities.
4. Generate small Alembic migrations for reviewed schema changes only.
   `F4-001` adds `0002_core_team_player_season.py`.
5. Add SQLAlchemy repositories/loaders that upsert by stable natural keys.
   `F4-002` implements the first core identity and membership slice.
6. Run database integration validation against local PostgreSQL only after the
   migration is explicitly approved.
7. Migrate stats and loader behavior gradually after parser outputs are stable.
8. Remove Peewee only after equivalent SQLAlchemy paths exist and the owner
   explicitly approves removal.

## Peewee Coexistence

During coexistence:

- new DB code uses SQLAlchemy 2.0 and Alembic;
- no new Peewee models or `create_tables()` flows are added;
- legacy imports from `scrape_main.py`, `models/`, `db_manager/`, and `scrap/`
  remain available for existing tests and manual legacy workflows;
- SQLAlchemy loaders must not call legacy Peewee operations;
- shared concepts such as teams, players, and seasons are documented before any
  crosswalk is implemented.

## Future Constraints And Indexes

The current foundation is enough for Phase 2 planning. Future reviewed
migrations may add:

- non-null constraints after source coverage proves identifiers are reliable;
- indexes for common lookups by Basketball Reference IDs and season;
- explicit tables for player-team-season and player-season stats;
- constraints that separate real team rows from synthetic source markers;
- source lineage columns that connect loaded rows back to `raw.raw_pages`.

Any migration that changes existing tables must include downgrade behavior where
practical and must be tested without live scraping.

## Validation Plan

Before implementation in a future phase:

- validate parser and normalizer output without network access;
- run duplicate-key checks before loading;
- run `uv run ruff check .` and `uv run pytest`;
- run Alembic checks only when local PostgreSQL is intentionally available;
- document any required local database setup in the phase that introduces DB
  integration validation.

## Out Of Scope For Phase 2

- Applying Alembic migrations.
- Writing to local or production databases.
- Implementing full SQLAlchemy loaders.
- Deleting Peewee or legacy scraper code.
- Running live scraping or contacting Basketball Reference.
- Activating Phase 3 or approving future-phase tasks.
