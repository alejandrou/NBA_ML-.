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

## Team Name Selector Contract

The parser also reads the display name from the page heading using the explicit
selector contract `h1 > span:nth-of-type(2)`: the page must contain an `h1`
with exactly three direct `span` elements, and the second span is the team name.
The first span is the season label and the third is the page suffix (`Roster and
Stats`) in the measured archive. The parsed and normalized page results expose
`team_name` and `team_name_issues` metadata; the name is not mixed into a stat
row.

Missing headings, a span count other than three, and an empty second span each
produce a named `team_name_*` issue and leave `team_name` unset. These are
non-fatal page degradations: the team-season stats still proceed through
validation and loading, so the loader's existing abbreviation fallback remains
available while the issue stays visible in the offline processing report.

When a caller supplies `team_name_by_source`, a valid name derived from the page
takes precedence. A disagreement records `team_name_override_disagreement`
with both values; a caller value is still available as a curated fallback when
the page cannot provide a name.

The serialized processing report summarizes these non-fatal warnings with
`team_name_issue_count` and a deterministic `team_name_issue_counts` mapping by
issue code. Full issue messages and source context remain on each entry.

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

- Team-season pages handle real team rows only.
- Synthetic codes — `TOT` and any multi-team marker, meaning a numeric team
  count of at least two followed by `TM` — must not be emitted as real
  team-season rows. The check constraints on `core.teams`,
  `core.team_aliases`, and `core.team_seasons` reject them in the database too.
- Full player-season aggregate rows are future player-page scope, not
  team-season page scope.
- `player_name` is descriptive only and must not be used as a stable key.
- `basketball_reference_player_id` is the stable player identifier when
  available.
- Missing player IDs are represented as `identifier_status="missing_player_id"`
  so validation or future loaders can quarantine the row instead of inventing a
  key.

## Data Quality Checks

`validate_normalized_team_season_rows(...)` reports issues for:

- missing basic context such as `source_table`, `season_year`, or `stat_scope`;
- synthetic team-code rows that appear in team-season output;
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

Team summary tables, salary tables, frontend, and generated metrics remain out
of scope. Postseason tables, database loading, migrations, and the API have
since shipped outside this document's Phase 3 scope.

The player-page pipeline exists as a separate path from team-season parsing:
`scraping/parsers/player_page.py`, `scraping/normalizers/player_page.py`,
`db/loaders/player_page_stats.py`,
`scraping/offline_player_stats_backfill.py`, and
`scraping/offline_player_postseason_stats_backfill.py`. It owns full
player-season aggregate rows — `stats.player_season_*` and
`stats.player_team_season_*` for regular season,
`stats.player_postseason_*` and `stats.player_team_postseason_*` for
postseason (the latter added by migration `0005_postseason_stats_tables`).
Current player rows from team-season pages (roster, totals, advanced tables)
are unaffected by this document and continue to have
`basketball_reference_player_id` extracted from player links when present.
