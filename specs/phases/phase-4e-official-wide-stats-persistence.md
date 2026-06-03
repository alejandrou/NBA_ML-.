# Phase 4E - Official Basketball Reference Wide Stats Persistence

Status: proposed
Phase ID: `phase-4e-official-wide-stats-persistence`

## Goal

Prepare and then implement a relational `stats` schema for official Basketball
Reference player statistics from cached NBA team-season pages.

The phase keeps identity and membership in `core`, official scraped statistics
in `stats`, and future app-generated metrics in `features`.

The target flow is:

```text
cached team-season HTML
-> parse
-> normalize
-> validate
-> load core identities
-> load official wide stats
-> stats validation checks
```

## Preconditions

- Phase 4D is reviewed and closed or the owner explicitly approves starting
  this proposed phase while Phase 4D remains active.
- Core identity tables exist and are migrated:
  `core.seasons`, `core.teams`, `core.team_aliases`, `core.team_seasons`,
  `core.players`, `core.player_seasons`, and
  `core.player_team_seasons`.
- The offline cached HTML processing and loading path remains cache-only and
  no live scraping is required for this phase.

## Phase Tasks

- `F4E-001`: Official wide stats schema plan.
- `F4E-002`: Stats models and Alembic migration.
- `F4E-003`: Idempotent stats repositories.
- `F4E-004`: Normalized rows to wide stats loader.
- `F4E-005`: Offline stats backfill command.
- `F4E-006`: Official stats validation checks.

All F4E tasks stay `pending` until F4E becomes the current phase and the owner
approves promotion according to phase governance.

## Schema Decisions

- Use separate tables for real team stints and `TOT` aggregates.
- Real-team stat tables FK to `core.player_team_seasons.id`.
- Aggregate `TOT` stat tables FK to `core.player_seasons.id`.
- `stats.player_team_season_roster` is team-stint only and FKs to
  `core.player_team_seasons.id`.
- Team-stint wide tables:
  `player_team_season_totals`, `player_team_season_per_game`,
  `player_team_season_per_minute`, `player_team_season_per_poss`,
  `player_team_season_advanced`, `player_team_season_shooting`,
  `player_team_season_adj_shooting`, and `player_team_season_pbp`.
- Aggregate wide tables:
  `player_season_totals`, `player_season_per_game`,
  `player_season_per_minute`, `player_season_per_poss`,
  `player_season_advanced`, `player_season_shooting`,
  `player_season_adj_shooting`, and `player_season_pbp`.
- No `JSONB` as primary stat storage. Official parser keys become typed
  columns.
- Before freezing final columns, inspect the normalized keys emitted by the
  current normalizer for each supported `source_table`.
- Numeric counts use integers.
- Rates, percentages, and advanced values use numeric decimals.
- Official text fields such as awards, college, position, height text, and
  experience text remain strings where needed.
- Stat columns are nullable by default to support older seasons and
  unavailable official fields.
- FK and unique grain columns are non-null.
- Each wide table has a surrogate primary key plus a unique FK constraint at
  its grain.

## Allowed Work

- Design official wide stats tables under the `stats` schema.
- Add SQLAlchemy 2.0 models and Alembic migrations only in the approved model
  task.
- Add idempotent stats repositories and loaders only after the schema plan is
  accepted.
- Load official stats only from already parsed, normalized, and validated rows.
- Add validation checks for counts, duplicates, FK integrity, `TOT` separation,
  nullability, and numeric ranges.

## Disallowed Work

- Live scraping, cache refresh, or Basketball Reference contact.
- Treating `TOT` as a real team.
- Using `player_name` as a stable key.
- Storing official stats primarily as `JSONB`.
- Mixing generated metrics, OVR, rankings, similarity, recommendations, or ML
  features into `stats`.
- API or frontend implementation.
- Peewee or legacy code deletion.
- Destructive migrations or data deletion without explicit owner approval.
- Branch creation, commits, pushes, or PRs without explicit owner approval.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`
