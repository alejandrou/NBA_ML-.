# F4E-001 - Official Wide Stats Schema Plan

## Goal

Finalize a reviewed relational schema plan for official Basketball Reference
player statistics before any SQLAlchemy models, Alembic migrations, loaders, or
database writes are implemented.

## Scope

This task is documentation-only. It activates Phase 4E and closes the schema
design enough for `F4E-002` to implement models and migration without
redesigning the `stats` schema.

Allowed:

- update schema, feature, roadmap, progress, review, and learning docs;
- update task status for Phase 4E activation and `F4E-001` review readiness;
- inspect local cached HTML and parser/normalizer output without network or DB
  writes.

Not allowed:

- SQLAlchemy stats models;
- Alembic migrations;
- stats repositories;
- stats loaders;
- stats backfill command;
- database writes;
- live scraping, acquisition, or cache refresh;
- API, frontend, OVR, ranking, similarity, recommendations, or ML work.

## Requirements

- Document the `core` / `stats` / `features` separation in
  `docs/architecture/OFFICIAL_STATS_SCHEMA.md`.
- Confirm Phase 4D is closed using the owner-confirmed core counts and
  `docs/validation/OFFLINE_DATABASE_PREPARATION.md`.
- Inspect normalized keys emitted by the current parser/normalizer for every
  supported `source_table`: `roster`, `totals`, `per_game`, `per_minute`,
  `per_poss`, `advanced`, `shooting`, `adj_shooting`, and `pbp`.
- Define wide typed target tables for real team stints and separate aggregate
  `TOT` target tables.
- Define exactly 17 additive `stats` tables:
  `stats.player_team_season_roster`, 8 team-stint stats tables, and 8
  player-season aggregate stats tables.
- Use `core.player_team_seasons.id` as the FK grain for roster and real-team
  stats.
- Use `core.player_seasons.id` as the FK grain for aggregate player-season
  stats, including official `TOT` rows.
- Keep `stats.player_team_season_roster` team-stint only.
- Require surrogate primary keys, non-null FK grain columns, lineage columns,
  and unique FK constraints on every wide table.
- Add lineage columns on every table: `source_url`, `cache_path`,
  `parser_version`, `created_at`, and `updated_at`.
- Map count fields to `Integer`, rate/percentage/advanced fields to
  `Numeric(10, 4)`, official display text fields to `String`, URL/path fields
  to `Text`, parsed dates to `Date`, and timestamps to
  `DateTime(timezone=True)`.
- Mark official stat columns nullable by default.
- Reject `JSONB` as primary stat storage.
- Review legacy `player_stats`, `player_advanced`, and roster ideas without
  copying legacy Peewee identity mistakes.

## Observed-Key Inspection

The schema plan uses normalized keys inspected from:

- local cache inventory: 775 valid cached NBA team-season pages;
- parser: `src/nba_data/scraping/parsers/team_season.py`;
- normalizer: `src/nba_data/scraping/normalizers/team_season.py`;
- sample: ATL cached team-season pages for season end years 2000, 2005, 2010,
  2015, 2020, and 2025.

The inspected sample emitted all expected source families and no unexpected
families. It did not emit `TOT` aggregate rows, so the design supports `TOT`
from the current normalizer contract but does not claim current team-season
pages produce those rows.

Final normalized-key to DB-column mappings are documented in
`docs/architecture/OFFICIAL_STATS_SCHEMA.md`.

## Acceptance Criteria

- Phase spec exists at
  `specs/phases/phase-4e-official-wide-stats-persistence.md`.
- Design doc exists at `docs/architecture/OFFICIAL_STATS_SCHEMA.md`.
- Legacy review exists at `docs/migration/LEGACY_STATS_SCHEMA_REVIEW.md`.
- The design lists all 17 final `stats` table names.
- The design documents table grain, FKs, unique constraints, lineage columns,
  nullability, and SQL type recommendations.
- The design has one section for each source family:
  `roster`, `totals`, `per_game`, `per_minute`, `per_poss`, `advanced`,
  `shooting`, `adj_shooting`, and `pbp`.
- The design records observed normalized keys and final
  `normalized key -> DB column` mappings.
- The design states that `TOT` is persisted only through player-season
  aggregate tables, not team tables.
- The design rejects `JSONB` as primary stat storage.
- `F4E-001` is left in `needs_review`, not `done`.
- `F4E-002` through `F4E-006` remain `pending`.
- No SQLAlchemy stats models, Alembic migrations, repositories, loaders,
  backfills, live scraping, cache refresh, or database writes are introduced.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`
