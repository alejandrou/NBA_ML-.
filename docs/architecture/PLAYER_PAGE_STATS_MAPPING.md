# Player Page Stats Mapping

## Purpose

This document maps Basketball Reference player-page table IDs to planned Phase
4E database tables. It is documentation only and does not implement parsers,
loaders, models, migrations, or backfills.

## Regular Season

| Player-page table ID | Player-season table | Team-stint relationship |
| --- | --- | --- |
| `per_game_stats` | `stats.player_season_per_game` | Team-season pages populate `stats.player_team_season_per_game`. |
| `totals_stats` | `stats.player_season_totals` | Team-season pages populate `stats.player_team_season_totals`. |
| `per_minute_stats` | `stats.player_season_per_minute` | Team-season pages populate `stats.player_team_season_per_minute`. |
| `per_poss` | `stats.player_season_per_poss` | Team-season pages populate `stats.player_team_season_per_poss`. |
| `advanced` | `stats.player_season_advanced` | Team-season pages populate `stats.player_team_season_advanced`. |
| `shooting` | `stats.player_season_shooting` | Team-season pages populate `stats.player_team_season_shooting`. |
| `adj_shooting` | `stats.player_season_adj_shooting` | Team-season pages populate `stats.player_team_season_adj_shooting`. |
| `pbp_stats` | `stats.player_season_pbp` | Team-season pages populate `stats.player_team_season_pbp`. |

`F4E-007` implements the regular-season mapping below through a cache-only
player-page parser, selector, loader, and guarded backfill command.

`source_team_code` on `stats.player_season_*` is metadata only. Valid source
examples include `BOS`, `HOU`, `BRK`, `2TM`, `3TM`, and `4TM`. Synthetic codes
must not create `core` team rows or team-stint stats rows.

For each player-season and supported regular-season stat table, load exactly
one full-season row into `stats.player_season_*`.

- If a `2TM`, `3TM`, or `4TM` row exists, use that synthetic multi-team row.
- If no synthetic multi-team row exists, use the single real-team row.
- For traded seasons, ignore player-page real-team stint rows for
  `stats.player_season_*`; those belong only to `stats.player_team_season_*`.
- Never insert `TOT`, `2TM`, `3TM`, or `4TM` into `core.teams`,
  `core.team_seasons`, `core.player_team_seasons`, or
  `stats.player_team_season_*`.

Examples:

- James Harden 2020-21:
  `2TM` -> `stats.player_season_*`
  `HOU` and `BRK` -> team-stint stats only
- Jaylen Brown 2023-24:
  `BOS` -> `stats.player_season_*` because there is no synthetic multi-team
  row.

## Postseason

| Player-page postseason table ID | Player postseason table | Team postseason table |
| --- | --- | --- |
| `per_game_stats_post` | `stats.player_postseason_per_game` | `stats.player_team_postseason_per_game` |
| `totals_stats_post` | `stats.player_postseason_totals` | `stats.player_team_postseason_totals` |
| `per_minute_stats_post` | `stats.player_postseason_per_minute` | `stats.player_team_postseason_per_minute` |
| `per_poss_post` | `stats.player_postseason_per_poss` | `stats.player_team_postseason_per_poss` |
| `advanced_post` | `stats.player_postseason_advanced` | `stats.player_team_postseason_advanced` |
| `shooting_post` | `stats.player_postseason_shooting` | `stats.player_team_postseason_shooting` |
| `adj_shooting_post` | `stats.player_postseason_adj_shooting` | `stats.player_team_postseason_adj_shooting` |
| `pbp_stats_post` | `stats.player_postseason_pbp` | `stats.player_team_postseason_pbp` |

Postseason tables are future separate `stats` families and must not be mixed
into regular-season tables.

## Out Of Scope

Do not persist these player-page areas as official Phase 4E season stats:

- Game Highs
- Last 5 Games
- Game logs
- Splits
- All-Star tables
- College tables
- Salaries
- Contracts
- Similarity scores

`TOT` is out of scope as a supported persisted player-page source row in Phase
4E.
