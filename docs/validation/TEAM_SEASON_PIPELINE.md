# Team Season Parser, Normalizer, and Validator

This document describes parsing, normalization, and validation for team-season
HTML that is already available to the pipeline. It does not acquire raw HTML,
refresh cache entries, run live scraping, or load the database.

## Supported Tables

Phase 3 supports these team-season page tables:

- `roster` from `roster`
- `totals` from `totals_stats`
- `per_game` from `per_game_stats`
- `per_minute` from `per_minute_stats`
- `per_poss` from `per_poss`
- `advanced` from `advanced`
- `shooting` from `shooting`
- `adj_shooting` from `adj_shooting`
- `pbp` from `pbp_stats`

Missing supported tables return an empty list. Parsers read visible tables and
tables hidden inside HTML comments, skip repeated `tbody` header rows, and
extract `basketball_reference_player_id` from player links when present.

## Normalized Row Shape

`normalize_team_season_page(...)` returns rows with:

- `league`
- `season_year`
- `team_abbreviation`
- `team_context`
- `source_table`
- `stat_scope`
- `player_name`
- `basketball_reference_player_id`
- `stable_player_key`
- `identifier_status`
- `values`

`values` contains conservative scraped values with snake-case keys. Numeric
conversion is limited to safe integers and floats. Generated metrics are not
mixed into normalized scraped stats.

## Domain Rules

- `TOT` is not a real team. It is normalized as `team_context="aggregate"` and
  `stat_scope="player_season_aggregate"`.
- `player_name` is descriptive only and must not be used as a stable key.
- `basketball_reference_player_id` is the stable player identifier when
  available.
- Missing player IDs are represented as `identifier_status="missing_player_id"`
  so validation or future loaders can quarantine the row instead of inventing a
  key.

## Data Quality Checks

`validate_normalized_team_season_rows(...)` reports issues for:

- missing basic context such as `source_table`, `season_year`, or `stat_scope`;
- `TOT` rows that are not classified as aggregates;
- player rows missing `basketball_reference_player_id` when stable IDs are
  required;
- duplicate natural keys within one normalized batch;
- required tables that have no normalized rows.

## Phase 4C Reporting And Quarantine

The offline Phase 4C report flow is:

```text
OfflineTeamSeasonProcessingReport + OfflineTeamSeasonLoadReport -> audit report
```

The audit report distinguishes parsed, validated, loaded, skipped, and
quarantined row counts. Validation failures keep invalid normalized rows out of
loader input while preserving them as quarantined rows with source context,
validation issues, and retry hints. Loader failures quarantine only the rows for
the failed entry; successful entries remain separate and can be retried safely
through the idempotent loader path.

Operator retry flow:

1. For validation quarantines, fix parser, normalizer, source metadata, or the
   cached HTML fixture, then rerun offline processing before loading.
2. For loading quarantines, fix the loader input or database-side issue, then
   rerun the same validated report through the idempotent loader path.
3. Compare the next audit report and confirm quarantined rows decrease without
   unexpected duplicate load effects.

## Known Gaps

Postseason tables, team summary tables, salary tables, database loading,
migrations, API, frontend, and generated metrics are out of Phase 3 scope.

There is no separate player-page pipeline yet. Current player rows are derived
from team-season pages such as roster, totals, and advanced tables, with
`basketball_reference_player_id` extracted from player links when present.
Dedicated Basketball Reference player pages remain future scope unless a later
manifest and parser task explicitly adds them.
