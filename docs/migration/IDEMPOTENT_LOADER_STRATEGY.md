# Idempotent Loader Strategy

## Purpose

This document defines the target loading strategy for parsed team-season data in
later phases. It is a design record only: Phase 2 does not write production
data, create loader repositories, or apply database migrations.

This document does not download raw HTML, parse HTML, or implement an offline
processor. It starts at the loader boundary: already parsed, normalized, and
validated rows are ready to be written idempotently.

## Pipeline Boundary

The target flow remains:

```text
cached HTML -> pure parser -> normalizer -> validator -> idempotent loader
```

- Cached HTML is the raw source of truth for repeatable parsing.
- Parsers receive HTML strings and do not touch the network or database.
- Normalizers convert parser rows into canonical records with explicit source
  metadata.
- Validators check row shape, required identifiers, duplicates, and domain
  rules before any database write.
- Loaders write only validated records and must be safe to rerun.

## Natural Keys

Future loaders should upsert by stable natural keys instead of transient row
order or display names.

- `core.seasons`: unique by `(league, season_year)`.
- `core.teams`: keyed by Basketball Reference team abbreviation or future
  stable team/franchise identifier, with aliases modeled separately.
- `core.team_aliases`: unique by `(team_id, abbreviation, from_season_year,
  to_season_year)`.
- `core.players`: unique by `basketball_reference_player_id` when available.
  `player_name` is descriptive only and must not be a stable primary key.
- Future team-season stat tables: unique by the narrowest stable grain, such as
  `(season_id, team_id, player_id, stat_scope)` for player-team-season rows.
- Future player-season aggregate tables: separate `TOT` aggregate rows from
  real team rows; `TOT` is not a team.

When a stable Basketball Reference player ID is unavailable, the loader should
reject or quarantine the row unless an explicitly documented matching strategy
has been reviewed.

## Rerun Behavior

Loaders must be idempotent for the same normalized input.

- Reprocessing the same cached page should update the same database rows rather
  than creating duplicates.
- Reprocessing newer parser output for the same source should preserve the
  natural key and update mutable fields only when the normalized value changes.
- Loader results should record enough source context to trace a row back to the
  cached page, parser version, and run metadata.
- Duplicate natural keys in one normalized batch should fail validation before
  any write.
- Partial failures should leave an auditable error state and avoid silent
  duplicate inserts on retry.

## Validation Before Loading

Future validation should run before database writes and stay separate from
parsing.

- Required identifiers are present at the expected grain.
- `TOT` rows are classified as aggregates, not teams.
- Player names are not used as stable keys.
- Numeric fields are parseable or explicitly marked as unavailable.
- Missing data distinguishes unavailable, not scraped, and parse error cases.
- Batch-level duplicate keys are reported with enough context to fix the parser
  or normalizer.

## Phase Boundaries

Phase 2 only documents the strategy. Later phases may add:

- normalization models for stable team-season parser output;
- data quality checks for normalized rows;
- SQLAlchemy repositories with upsert behavior;
- Alembic migrations for reviewed unique constraints and indexes;
- integration tests against local PostgreSQL.

Out of scope for this document are live scraping, production data writes, full
SQLAlchemy loader implementation, raw HTML download, offline HTML processing,
deleting Peewee code, and applying database migrations.
