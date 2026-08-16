# Player Page Stats Mapping

## Purpose

This document maps Basketball Reference player-page table IDs to planned Phase
4E database tables. It is documentation only and does not implement parsers,
loaders, models, migrations, or backfills.

## Season Labels And The Century Rollover

Player-page rows label a season as `YYYY-YY` (`1999-00`, `2024-25`), and
occasionally as `YYYY-YYYY` or as a plain four-digit year. Every stats row is
keyed on the **season end year**, so the label has to be resolved to one.

A `YYYY-YY` label may cross a century. `1999-00` ends in **2000**, not 1900, and
the archive opens on exactly that label. Derive the end year by comparison, not
by a hard-coded pivot:

- Start from the start year's century.
- If the two-digit suffix is numerically **below** the start year's last two
  digits, the label crossed a century — add 100.

So `1999-00` → 2000, `2000-01` → 2001, `2024-25` → 2025, `2099-00` → 2100. A
"two-digit years below 50 mean the 2000s" rule is wrong for this archive and
wrong again for the next one; do not reintroduce it.

Only `YYYY-YY`, `YYYY-YYYY`, and `YYYY` are accepted. Anything else — including a
three-digit suffix — resolves to no season year at all rather than to a guessed
one, and the row is skipped rather than keyed wrongly.

`_season_end_year` in `scraping/normalizers/player_page.py` owns this rule for
player pages. Team-season pages do not use it: their season end year comes from
the page URL.

Rows written before this rule was fixed carry `parser_version`
`player-page-parser-v1` / `player-page-postseason-parser-v1`; rows written after
carry `-v2`. Rows written after the multi-team marker became semantic (F4E-014)
carry `-v3`. Lineage queries must filter on the version they mean.

## Multi-Team Markers

A multi-team marker is a numeric team count of at least two followed by `TM`.
The set is open-ended, not the fixed list `{2TM, 3TM, 4TM}`. Measured over the
2,551 cached player pages, counting distinct `(player, season)` pairs whose
source team cell matches a numeric marker:

| Marker | Distinct player-seasons | Raw row occurrences |
| --- | --- | --- |
| `2TM` | 1,695 | 13,402 |
| `3TM` | 110 | 870 |
| `4TM` | 4 | 30 |
| `5TM` | 1 | 8 |

The single `5TM` is Bobby Jones (`jonesbo02`), 2007-08. No `0TM` and no `1TM`
appear anywhere in the cache, which is why the rule is a count of at least two
rather than "any digits". `is_multi_team_marker` in
`src/nba_data/domain/team_codes.py` owns this rule for every layer; `TOT` is
handled separately and is not a multi-team marker.

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
player-page parser, selector, loader, and guarded backfill command. The owner
accepted `F4E-007` as `done`, and `F4E-009` validates the final routing and
source-team-code safety rules.

`source_team_code` on `stats.player_season_*` is metadata only. Valid source
examples include `BOS`, `HOU`, `BRK`, and any multi-team marker such as `2TM`
or `5TM`. Synthetic codes must not create `core` team rows or team-stint stats
rows.

For each player-season and supported regular-season stat table, load exactly
one full-season row into `stats.player_season_*`.

- If a multi-team row exists, use that row.
- If no multi-team row exists, use the single real-team row.
- For traded seasons, ignore player-page real-team stint rows for
  `stats.player_season_*`; those belong only to `stats.player_team_season_*`.
- Never insert `TOT` or any multi-team marker into `core.teams`,
  `core.team_aliases`, `core.team_seasons`, `core.player_team_seasons`, or
  `stats.player_team_season_*`. The `ck_core_*_not_synthetic` check constraints
  enforce this in the database as well as in code.

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

`F4E-008` implements the postseason mapping below through a cache-only
player-page parser, selector, loader, and guarded backfill command. The owner
accepted `F4E-008` as `done`, and `F4E-009` validates the separation between
regular-season and postseason table families.

For each player-season and supported postseason stat table, load exactly one
aggregate row into `stats.player_postseason_*`.

- If a multi-team row exists, use that row for `stats.player_postseason_*`.
- If no multi-team row exists, use the single real-team row for
  `stats.player_postseason_*`.
- Load each real team row into `stats.player_team_postseason_*`.
- Never insert `TOT` or any multi-team marker into `core.teams`,
  `core.team_aliases`, `core.team_seasons`, `core.player_team_seasons`, or
  `stats.player_team_postseason_*`.

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
