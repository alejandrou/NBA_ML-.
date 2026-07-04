# Official Stats Schema

## Purpose

This document is the reviewed Phase 4E schema contract for official Basketball
Reference player statistics. It is documentation only: it does not add
SQLAlchemy models, Alembic migrations, repositories, loaders, backfills, or
database writes.

The project keeps a strict schema boundary:

```text
core = identity and relationships
stats = official scraped Basketball Reference statistics
features = app-generated metrics such as OVR, rankings, similarity,
           recommendations, and ML features
```

`core` remains the source of truth for seasons, teams, players, player seasons,
and player/team-season membership. `stats` stores official scraped stats as
typed wide relational columns. `features` remains reserved for generated
metrics and must not be mixed into `stats`.

## Source Inspection

F4E-001 inspected the current parser/normalizer boundary:

- Parser: `src/nba_data/scraping/parsers/team_season.py`
- Normalizer: `src/nba_data/scraping/normalizers/team_season.py`
- Offline inventory: 775 valid cached NBA team-season pages under
  `data/raw/html`.
- Sample used for observed keys: ATL cached team-season pages for season end
  years 2000, 2005, 2010, 2015, 2020, and 2025.

The current normalizer emits rows with context fields plus a `values` map.
`values` keys are snake-case forms of Basketball Reference `data-stat` keys.
F4E persists those official keys as typed columns; it must not use `JSONB` as
the primary stats model.

The inspected sample emitted these source tables:

```text
roster, totals, per_game, per_minute, per_poss, advanced, shooting,
adj_shooting, pbp
```

The inspected cached team-season pages populate team-stint stats only. They are
not the source of full player-season stats.

Future player-page parsing will populate `stats.player_season_*` from official
Basketball Reference player pages. Player-page rows use `source_team_code`
metadata such as `BOS`, `HOU`, `2TM`, `3TM`, or `4TM`; synthetic multi-team
codes are source markers only and must not become `core` teams.

## Global Contract

`F4E-002` created the initial 17 additive regular-season tables under schema
`stats`.

Roster:

- `stats.player_team_season_roster`

Team-stint stats:

- `stats.player_team_season_totals`
- `stats.player_team_season_per_game`
- `stats.player_team_season_per_minute`
- `stats.player_team_season_per_poss`
- `stats.player_team_season_advanced`
- `stats.player_team_season_shooting`
- `stats.player_team_season_adj_shooting`
- `stats.player_team_season_pbp`

Full player-season stats:

- `stats.player_season_totals`
- `stats.player_season_per_game`
- `stats.player_season_per_minute`
- `stats.player_season_per_poss`
- `stats.player_season_advanced`
- `stats.player_season_shooting`
- `stats.player_season_adj_shooting`
- `stats.player_season_pbp`

Every team-stint table, including roster, has:

- `id Integer primary key`
- `player_team_season_id Integer not null`
- FK `player_team_season_id -> core.player_team_seasons.id`
- unique constraint on `player_team_season_id`

Every current player-season table has:

- `id Integer primary key`
- `player_season_id Integer not null`
- FK `player_season_id -> core.player_seasons.id`
- unique constraint on `player_season_id`

Every table has the same lineage columns:

| Column | SQL type | Nullability | Notes |
| --- | --- | --- | --- |
| `source_url` | `Text` | not null | Basketball Reference source URL for the cached page. |
| `cache_path` | `Text` | not null | Local `.html.gz` cache path used for the row. |
| `parser_version` | `String(50)` | not null | Version label for parser/normalizer contract. |
| `created_at` | `DateTime(timezone=True)` | not null | Server default `func.now()` in F4E-002. |
| `updated_at` | `DateTime(timezone=True)` | not null | Server default `func.now()` and updated on update. |

The unique constraint backing index is the grain lookup index. Do not add a
duplicate non-unique FK index unless a later review finds a real query need.

`F4E-007` adds `source_team_code` to `stats.player_season_*` tables as
metadata only. It is not a foreign key and may contain either a real
Basketball Reference team code for single-team seasons or a synthetic
multi-team source marker such as `2TM`, `3TM`, or `4TM`.

`F4E-008` extends the schema with separate postseason `stats` tables while
keeping regular season and postseason rows fully separate.

`F4E-009` closes the reviewed validator contract over the final 33-table model.
The final validation pass checks table presence, grain integrity, synthetic
team-code safety, `source_team_code` metadata rules, corrected Basketball
Reference numeric scales, generated-metric absence, and regular-season versus
postseason lineage separation.

## Typing Rules

- Counts use `Integer`.
- Official rates, percentages, per-unit values, ratings, plus/minus values,
  win shares, and advanced values use `Numeric(10, 4)`.
- Official short text uses `String`, usually `String(20)` for positions and
  compact flags, `String(50)` for parser versions, and `String(200)` for names
  or awards.
- URLs and paths use `Text`.
- Parsed birth dates use `Date`.
- Timestamps use `DateTime(timezone=True)`.
- Statistic columns are nullable by default.
- PK, FK, unique grain, and lineage columns are non-null.

Missing known official columns are stored as `NULL`. Unknown normalized keys
not listed in this document are not silently stored; the F4E-004 loader must
report or quarantine them until the schema is reviewed.

## Source Team Code Rules

`TOT`, `2TM`, `3TM`, and `4TM` are not real teams.

- Team-season pages load real team rows only into `player_team_season_*`
  tables.
- Player pages load full player-season rows into `player_season_*` tables.
- For each player-season and supported stat table, load exactly one full-season
  row into `player_season_*`.
- Player-page `2TM`, `3TM`, and `4TM` rows load only into `player_season_*`
  tables as official full-season rows when present.
- If no `2TM`, `3TM`, or `4TM` row exists, the single real-team player-page
  row is the official full-season row.
- For traded seasons, do not load the player-page real-team stint rows into
  `player_season_*`; those real-team stint rows belong only to
  `player_team_season_*`.
- `TOT` must not be persisted as a real team or as the source for supported
  official season stats. Ignore `TOT` if it appears only in unsupported tables
  such as Game Highs.
- Do not use Game Highs, Last 5 Games, game logs, splits, All-Star, college,
  salary, contract, or similarity-score tables as official season-stat sources
  in Phase 4E.
- Do not synthesize full-season stats from team stints. Persist full-season
  stats only from official player-page rows.
- Stats loaders must not create missing `core` identities. Missing
  `core.player_team_seasons.id` or `core.player_seasons.id` is a loader failure
  or quarantine condition.

## Roster

Target table:

- Team-stint: `stats.player_team_season_roster`
- Player-season: none

Grain:

- FK: `player_team_season_id -> core.player_team_seasons.id`
- Unique constraint: `player_team_season_id`

Columns and mapping:

| Normalized key | DB column | SQL type |
| --- | --- | --- |
| `number` | `jersey_number` | `String(20)` |
| `player` | `player_name` | `String(200)` |
| `pos` | `position` | `String(20)` |
| `height` | `height` | `String(20)` |
| `weight` | `weight` | `Integer` |
| `birth_date` | `birth_date` | `Date` |
| `years_experience` | `experience` | `String(20)` |
| `college` | `college` | `String(200)` |
| `flag` | `country_flag` | `String(20)` |

Missing columns are stored as `NULL`. `birth_date` should be parsed from the
official display string when possible; blank or unparseable values remain
`NULL` and may be reported by validation if suspicious.

Legacy reference: legacy `models/player/player.py` is retained only as the
conceptual roster source. F4E improves it by using `core.player_team_seasons.id`
instead of player names, team names, loose years, or legacy roster rows as
identity.

## Totals

Target tables:

- Team-stint: `stats.player_team_season_totals`
- Player-season: `stats.player_season_totals`

Grain:

- Team-stint FK: `player_team_season_id -> core.player_team_seasons.id`
- Player-season FK: `player_season_id -> core.player_seasons.id`
- Unique constraint: the table's FK grain

Columns and mapping:

| Normalized key | DB column | SQL type |
| --- | --- | --- |
| `ranker` | `rk` | `Integer` |
| `name_display` | `player_name_display` | `String(200)` |
| `age` | `age` | `Integer` |
| `games` | `g` | `Integer` |
| `games_started` | `gs` | `Integer` |
| `mp` | `mp` | `Integer` |
| `fg` | `fg` | `Integer` |
| `fga` | `fga` | `Integer` |
| `fg_pct` | `fg_pct` | `Numeric(10, 4)` |
| `fg3` | `fg3` | `Integer` |
| `fg3a` | `fg3a` | `Integer` |
| `fg3_pct` | `fg3_pct` | `Numeric(10, 4)` |
| `fg2` | `fg2` | `Integer` |
| `fg2a` | `fg2a` | `Integer` |
| `fg2_pct` | `fg2_pct` | `Numeric(10, 4)` |
| `efg_pct` | `efg_pct` | `Numeric(10, 4)` |
| `ft` | `ft` | `Integer` |
| `fta` | `fta` | `Integer` |
| `ft_pct` | `ft_pct` | `Numeric(10, 4)` |
| `orb` | `orb` | `Integer` |
| `drb` | `drb` | `Integer` |
| `trb` | `trb` | `Integer` |
| `ast` | `ast` | `Integer` |
| `stl` | `stl` | `Integer` |
| `blk` | `blk` | `Integer` |
| `tov` | `tov` | `Integer` |
| `pf` | `pf` | `Integer` |
| `pts` | `pts` | `Integer` |
| `tpl_dbl` | `tpl_dbl` | `Integer` |
| `awards` | `awards` | `String(200)` |

Missing columns are stored as `NULL`. Player-page full-season rows load into
`stats.player_season_totals`.

Legacy reference: legacy `models/player/player_stats.py` corresponds
conceptually to totals. F4E keeps the official totals meaning but rejects
name-based lookup, loose `year`, FK to legacy roster identity, string
percentages, and non-idempotent inserts.

## Per Game

Target tables:

- Team-stint: `stats.player_team_season_per_game`
- Player-season: `stats.player_season_per_game`

Grain:

- Team-stint FK: `player_team_season_id -> core.player_team_seasons.id`
- Player-season FK: `player_season_id -> core.player_seasons.id`
- Unique constraint: the table's FK grain

Columns and mapping:

| Normalized key | DB column | SQL type |
| --- | --- | --- |
| `ranker` | `rk` | `Integer` |
| `name_display` | `player_name_display` | `String(200)` |
| `pos` | `position` | `String(20)` |
| `age` | `age` | `Integer` |
| `games` | `g` | `Integer` |
| `games_started` | `gs` | `Integer` |
| `mp_per_g` | `mp_per_game` | `Numeric(10, 4)` |
| `fg_per_g` | `fg_per_game` | `Numeric(10, 4)` |
| `fga_per_g` | `fga_per_game` | `Numeric(10, 4)` |
| `fg_pct` | `fg_pct` | `Numeric(10, 4)` |
| `fg3_per_g` | `fg3_per_game` | `Numeric(10, 4)` |
| `fg3a_per_g` | `fg3a_per_game` | `Numeric(10, 4)` |
| `fg3_pct` | `fg3_pct` | `Numeric(10, 4)` |
| `fg2_per_g` | `fg2_per_game` | `Numeric(10, 4)` |
| `fg2a_per_g` | `fg2a_per_game` | `Numeric(10, 4)` |
| `fg2_pct` | `fg2_pct` | `Numeric(10, 4)` |
| `efg_pct` | `efg_pct` | `Numeric(10, 4)` |
| `ft_per_g` | `ft_per_game` | `Numeric(10, 4)` |
| `fta_per_g` | `fta_per_game` | `Numeric(10, 4)` |
| `ft_pct` | `ft_pct` | `Numeric(10, 4)` |
| `orb_per_g` | `orb_per_game` | `Numeric(10, 4)` |
| `drb_per_g` | `drb_per_game` | `Numeric(10, 4)` |
| `trb_per_g` | `trb_per_game` | `Numeric(10, 4)` |
| `ast_per_g` | `ast_per_game` | `Numeric(10, 4)` |
| `stl_per_g` | `stl_per_game` | `Numeric(10, 4)` |
| `blk_per_g` | `blk_per_game` | `Numeric(10, 4)` |
| `tov_per_g` | `tov_per_game` | `Numeric(10, 4)` |
| `pf_per_g` | `pf_per_game` | `Numeric(10, 4)` |
| `pts_per_g` | `pts_per_game` | `Numeric(10, 4)` |
| `awards` | `awards` | `String(200)` |

Missing columns are stored as `NULL`. Player-page full-season rows load into
`stats.player_season_per_game`.

Legacy reference: legacy did not have a dedicated per-game table. F4E stores
official per-game values separately instead of deriving them or mixing them
with totals.

## Per Minute

Target tables:

- Team-stint: `stats.player_team_season_per_minute`
- Player-season: `stats.player_season_per_minute`

Grain:

- Team-stint FK: `player_team_season_id -> core.player_team_seasons.id`
- Player-season FK: `player_season_id -> core.player_seasons.id`
- Unique constraint: the table's FK grain

Columns and mapping:

| Normalized key | DB column | SQL type |
| --- | --- | --- |
| `ranker` | `rk` | `Integer` |
| `name_display` | `player_name_display` | `String(200)` |
| `pos` | `position` | `String(20)` |
| `age` | `age` | `Integer` |
| `games` | `g` | `Integer` |
| `games_started` | `gs` | `Integer` |
| `mp` | `mp` | `Integer` |
| `fg_per_minute_36` | `fg_per_36` | `Numeric(10, 4)` |
| `fga_per_minute_36` | `fga_per_36` | `Numeric(10, 4)` |
| `fg_pct` | `fg_pct` | `Numeric(10, 4)` |
| `fg3_per_minute_36` | `fg3_per_36` | `Numeric(10, 4)` |
| `fg3a_per_minute_36` | `fg3a_per_36` | `Numeric(10, 4)` |
| `fg3_pct` | `fg3_pct` | `Numeric(10, 4)` |
| `fg2_per_minute_36` | `fg2_per_36` | `Numeric(10, 4)` |
| `fg2a_per_minute_36` | `fg2a_per_36` | `Numeric(10, 4)` |
| `fg2_pct` | `fg2_pct` | `Numeric(10, 4)` |
| `efg_pct` | `efg_pct` | `Numeric(10, 4)` |
| `ft_per_minute_36` | `ft_per_36` | `Numeric(10, 4)` |
| `fta_per_minute_36` | `fta_per_36` | `Numeric(10, 4)` |
| `ft_pct` | `ft_pct` | `Numeric(10, 4)` |
| `orb_per_minute_36` | `orb_per_36` | `Numeric(10, 4)` |
| `drb_per_minute_36` | `drb_per_36` | `Numeric(10, 4)` |
| `trb_per_minute_36` | `trb_per_36` | `Numeric(10, 4)` |
| `ast_per_minute_36` | `ast_per_36` | `Numeric(10, 4)` |
| `stl_per_minute_36` | `stl_per_36` | `Numeric(10, 4)` |
| `blk_per_minute_36` | `blk_per_36` | `Numeric(10, 4)` |
| `tov_per_minute_36` | `tov_per_36` | `Numeric(10, 4)` |
| `pf_per_minute_36` | `pf_per_36` | `Numeric(10, 4)` |
| `pts_per_minute_36` | `pts_per_36` | `Numeric(10, 4)` |
| `awards` | `awards` | `String(200)` |

Missing columns are stored as `NULL`. Player-page full-season rows load into
`stats.player_season_per_minute`.

Legacy reference: legacy did not have a dedicated per-minute table. F4E stores
the official Basketball Reference per-36 values directly rather than deriving
them from totals during load.

## Per Possession

Target tables:

- Team-stint: `stats.player_team_season_per_poss`
- Player-season: `stats.player_season_per_poss`

Grain:

- Team-stint FK: `player_team_season_id -> core.player_team_seasons.id`
- Player-season FK: `player_season_id -> core.player_seasons.id`
- Unique constraint: the table's FK grain

Columns and mapping:

| Normalized key | DB column | SQL type |
| --- | --- | --- |
| `ranker` | `rk` | `Integer` |
| `name_display` | `player_name_display` | `String(200)` |
| `age` | `age` | `Integer` |
| `games` | `g` | `Integer` |
| `games_started` | `gs` | `Integer` |
| `mp` | `mp` | `Integer` |
| `fg_per_poss` | `fg_per_poss` | `Numeric(10, 4)` |
| `fga_per_poss` | `fga_per_poss` | `Numeric(10, 4)` |
| `fg_pct` | `fg_pct` | `Numeric(10, 4)` |
| `fg3_per_poss` | `fg3_per_poss` | `Numeric(10, 4)` |
| `fg3a_per_poss` | `fg3a_per_poss` | `Numeric(10, 4)` |
| `fg3_pct` | `fg3_pct` | `Numeric(10, 4)` |
| `fg2_per_poss` | `fg2_per_poss` | `Numeric(10, 4)` |
| `fg2a_per_poss` | `fg2a_per_poss` | `Numeric(10, 4)` |
| `fg2_pct` | `fg2_pct` | `Numeric(10, 4)` |
| `efg_pct` | `efg_pct` | `Numeric(10, 4)` |
| `ft_per_poss` | `ft_per_poss` | `Numeric(10, 4)` |
| `fta_per_poss` | `fta_per_poss` | `Numeric(10, 4)` |
| `ft_pct` | `ft_pct` | `Numeric(10, 4)` |
| `orb_per_poss` | `orb_per_poss` | `Numeric(10, 4)` |
| `drb_per_poss` | `drb_per_poss` | `Numeric(10, 4)` |
| `trb_per_poss` | `trb_per_poss` | `Numeric(10, 4)` |
| `ast_per_poss` | `ast_per_poss` | `Numeric(10, 4)` |
| `stl_per_poss` | `stl_per_poss` | `Numeric(10, 4)` |
| `blk_per_poss` | `blk_per_poss` | `Numeric(10, 4)` |
| `tov_per_poss` | `tov_per_poss` | `Numeric(10, 4)` |
| `pf_per_poss` | `pf_per_poss` | `Numeric(10, 4)` |
| `pts_per_poss` | `pts_per_poss` | `Numeric(10, 4)` |
| `off_rtg` | `ortg` | `Numeric(10, 4)` |
| `def_rtg` | `drtg` | `Numeric(10, 4)` |
| `awards` | `awards` | `String(200)` |

Missing columns are stored as `NULL`. Player-page full-season rows load into
`stats.player_season_per_poss`.

Legacy reference: legacy did not have a dedicated per-possession table. F4E
stores the official per-possession values separately and keeps offensive and
defensive ratings as official stats, not generated features.

## Advanced

Target tables:

- Team-stint: `stats.player_team_season_advanced`
- Player-season: `stats.player_season_advanced`

Grain:

- Team-stint FK: `player_team_season_id -> core.player_team_seasons.id`
- Player-season FK: `player_season_id -> core.player_seasons.id`
- Unique constraint: the table's FK grain

Columns and mapping:

| Normalized key | DB column | SQL type |
| --- | --- | --- |
| `ranker` | `rk` | `Integer` |
| `name_display` | `player_name_display` | `String(200)` |
| `pos` | `position` | `String(20)` |
| `age` | `age` | `Integer` |
| `games` | `g` | `Integer` |
| `games_started` | `gs` | `Integer` |
| `mp` | `mp` | `Integer` |
| `per` | `per` | `Numeric(10, 4)` |
| `ts_pct` | `ts_pct` | `Numeric(10, 4)` |
| `fg3a_per_fga_pct` | `fg3a_per_fga_pct` | `Numeric(10, 4)` |
| `fta_per_fga_pct` | `fta_per_fga_pct` | `Numeric(10, 4)` |
| `orb_pct` | `orb_pct` | `Numeric(10, 4)` |
| `drb_pct` | `drb_pct` | `Numeric(10, 4)` |
| `trb_pct` | `trb_pct` | `Numeric(10, 4)` |
| `ast_pct` | `ast_pct` | `Numeric(10, 4)` |
| `stl_pct` | `stl_pct` | `Numeric(10, 4)` |
| `blk_pct` | `blk_pct` | `Numeric(10, 4)` |
| `tov_pct` | `tov_pct` | `Numeric(10, 4)` |
| `usg_pct` | `usg_pct` | `Numeric(10, 4)` |
| `ows` | `ows` | `Numeric(10, 4)` |
| `dws` | `dws` | `Numeric(10, 4)` |
| `ws` | `ws` | `Numeric(10, 4)` |
| `ws_per_48` | `ws_per_48` | `Numeric(10, 4)` |
| `obpm` | `obpm` | `Numeric(10, 4)` |
| `dbpm` | `dbpm` | `Numeric(10, 4)` |
| `bpm` | `bpm` | `Numeric(10, 4)` |
| `vorp` | `vorp` | `Numeric(10, 4)` |
| `awards` | `awards` | `String(200)` |

Missing columns are stored as `NULL`. Player-page full-season rows load into
`stats.player_season_advanced`.

Legacy reference: legacy `models/player/player_advanced.py` corresponds
conceptually to advanced stats. F4E keeps the semantic coverage but stores
numbers as numeric columns, uses reviewed `core` identity, and keeps advanced
official stats separate from future generated ratings.

## Shooting

Target tables:

- Team-stint: `stats.player_team_season_shooting`
- Player-season: `stats.player_season_shooting`

Grain:

- Team-stint FK: `player_team_season_id -> core.player_team_seasons.id`
- Player-season FK: `player_season_id -> core.player_seasons.id`
- Unique constraint: the table's FK grain

Columns and mapping:

| Normalized key | DB column | SQL type |
| --- | --- | --- |
| `ranker` | `rk` | `Integer` |
| `name_display` | `player_name_display` | `String(200)` |
| `pos` | `position` | `String(20)` |
| `age` | `age` | `Integer` |
| `games` | `g` | `Integer` |
| `games_started` | `gs` | `Integer` |
| `mp` | `mp` | `Integer` |
| `fg_pct` | `fg_pct` | `Numeric(10, 4)` |
| `avg_dist` | `avg_dist` | `Numeric(10, 4)` |
| `pct_fga_fg2a` | `pct_fga_fg2a` | `Numeric(10, 4)` |
| `pct_fga_00_03` | `pct_fga_0_3` | `Numeric(10, 4)` |
| `pct_fga_03_10` | `pct_fga_3_10` | `Numeric(10, 4)` |
| `pct_fga_10_16` | `pct_fga_10_16` | `Numeric(10, 4)` |
| `pct_fga_16_xx` | `pct_fga_16_plus` | `Numeric(10, 4)` |
| `pct_fga_fg3a` | `pct_fga_fg3a` | `Numeric(10, 4)` |
| `fg_pct_fg2a` | `fg_pct_fg2a` | `Numeric(10, 4)` |
| `fg_pct_00_03` | `fg_pct_0_3` | `Numeric(10, 4)` |
| `fg_pct_03_10` | `fg_pct_3_10` | `Numeric(10, 4)` |
| `fg_pct_10_16` | `fg_pct_10_16` | `Numeric(10, 4)` |
| `fg_pct_16_xx` | `fg_pct_16_plus` | `Numeric(10, 4)` |
| `fg_pct_fg3a` | `fg_pct_fg3a` | `Numeric(10, 4)` |
| `pct_ast_fg2` | `pct_ast_fg2` | `Numeric(10, 4)` |
| `pct_ast_fg3` | `pct_ast_fg3` | `Numeric(10, 4)` |
| `pct_fga_dunk` | `pct_fga_dunk` | `Numeric(10, 4)` |
| `fg_dunk` | `dunks_made` | `Integer` |
| `pct_fg3a_corner3` | `pct_fg3a_corner3` | `Numeric(10, 4)` |
| `fg_pct_corner3` | `fg_pct_corner3` | `Numeric(10, 4)` |
| `fg3_heave` | `heaves_made` | `Integer` |
| `fg3a_heave` | `heaves_att` | `Integer` |
| `awards` | `awards` | `String(200)` |

Missing columns are stored as `NULL`. Player-page full-season rows load into
`stats.player_season_shooting`.

Legacy reference: legacy did not have a dedicated shooting table. F4E stores
official shooting splits as official stats and does not infer shot profile
features in this schema.

## Adjusted Shooting

Target tables:

- Team-stint: `stats.player_team_season_adj_shooting`
- Player-season: `stats.player_season_adj_shooting`

Grain:

- Team-stint FK: `player_team_season_id -> core.player_team_seasons.id`
- Player-season FK: `player_season_id -> core.player_seasons.id`
- Unique constraint: the table's FK grain

Columns and mapping:

| Normalized key | DB column | SQL type |
| --- | --- | --- |
| `ranker` | `rk` | `Integer` |
| `name_display` | `player_name_display` | `String(200)` |
| `pos` | `position` | `String(20)` |
| `age` | `age` | `Integer` |
| `games` | `g` | `Integer` |
| `games_started` | `gs` | `Integer` |
| `mp` | `mp` | `Integer` |
| `fg_pct` | `fg_pct` | `Numeric(10, 4)` |
| `adj_fg_pct` | `adj_fg_pct` | `Numeric(10, 4)` |
| `fg2_pct` | `fg2_pct` | `Numeric(10, 4)` |
| `adj_fg2_pct` | `adj_fg2_pct` | `Numeric(10, 4)` |
| `fg3_pct` | `fg3_pct` | `Numeric(10, 4)` |
| `adj_fg3_pct` | `adj_fg3_pct` | `Numeric(10, 4)` |
| `efg_pct` | `efg_pct` | `Numeric(10, 4)` |
| `adj_efg_pct` | `adj_efg_pct` | `Numeric(10, 4)` |
| `ft_pct` | `ft_pct` | `Numeric(10, 4)` |
| `adj_ft_pct` | `adj_ft_pct` | `Numeric(10, 4)` |
| `ts_pct` | `ts_pct` | `Numeric(10, 4)` |
| `adj_ts_pct` | `adj_ts_pct` | `Numeric(10, 4)` |
| `fg3a_per_fga_pct` | `fg3a_per_fga_pct` | `Numeric(10, 4)` |
| `adj_fg3a_per_fga_pct` | `adj_fg3a_per_fga_pct` | `Numeric(10, 4)` |
| `fta_per_fga_pct` | `fta_per_fga_pct` | `Numeric(10, 4)` |
| `adj_fta_per_fga_pct` | `adj_fta_per_fga_pct` | `Numeric(10, 4)` |
| `fg_pts_added` | `fg_pts_added` | `Numeric(10, 4)` |
| `ts_pts_added` | `ts_pts_added` | `Numeric(10, 4)` |
| `awards` | `awards` | `String(200)` |

Missing columns are stored as `NULL`. Player-page full-season rows load into
`stats.player_season_adj_shooting`.

Legacy reference: legacy did not have a dedicated adjusted-shooting table.
F4E stores these official adjusted values as scraped stats and keeps future
custom shooting adjustments out of `stats`.

## Play By Play

Target tables:

- Team-stint: `stats.player_team_season_pbp`
- Player-season: `stats.player_season_pbp`

Grain:

- Team-stint FK: `player_team_season_id -> core.player_team_seasons.id`
- Player-season FK: `player_season_id -> core.player_seasons.id`
- Unique constraint: the table's FK grain

Columns and mapping:

| Normalized key | DB column | SQL type |
| --- | --- | --- |
| `ranker` | `rk` | `Integer` |
| `name_display` | `player_name_display` | `String(200)` |
| `pos` | `position` | `String(20)` |
| `age` | `age` | `Integer` |
| `games` | `g` | `Integer` |
| `games_started` | `gs` | `Integer` |
| `mp` | `mp` | `Integer` |
| `pct_1` | `pct_pg` | `Numeric(10, 4)` |
| `pct_2` | `pct_sg` | `Numeric(10, 4)` |
| `pct_3` | `pct_sf` | `Numeric(10, 4)` |
| `pct_4` | `pct_pf` | `Numeric(10, 4)` |
| `pct_5` | `pct_c` | `Numeric(10, 4)` |
| `plus_minus_on` | `on_court_plus_minus` | `Numeric(10, 4)` |
| `plus_minus_net` | `net_plus_minus` | `Numeric(10, 4)` |
| `tov_bad_pass` | `bad_pass_turnover` | `Integer` |
| `tov_lost_ball` | `lost_ball_turnover` | `Integer` |
| `fouls_shooting` | `fouls_shooting` | `Integer` |
| `fouls_offensive` | `fouls_offensive` | `Integer` |
| `drawn_shooting` | `drawn_shooting` | `Integer` |
| `drawn_offensive` | `drawn_offensive` | `Integer` |
| `and1s` | `and1s` | `Integer` |
| `own_shots_blk` | `own_shots_blocked` | `Integer` |
| `astd_pts` | `assisted_points` | `Integer` |
| `awards` | `awards` | `String(200)` |

Missing columns are stored as `NULL`. Player-page full-season rows load into
`stats.player_season_pbp`.

Legacy reference: legacy did not have a dedicated play-by-play-derived season
stats table. F4E stores only the official Basketball Reference season-level PBP
columns and does not introduce game logs or boxscores.

## Player-Page Source Mapping

`docs/architecture/PLAYER_PAGE_STATS_MAPPING.md` is the compact source mapping
for future player-page work. It maps Basketball Reference player-page table IDs
to regular-season `stats.player_season_*` tables, the corresponding
team-season table family, and future postseason tables.

Regular-season player-page table IDs implemented by `F4E-007`:

- `per_game_stats`
- `totals_stats`
- `per_minute_stats`
- `per_poss`
- `advanced`
- `shooting`
- `adj_shooting`
- `pbp_stats`

Postseason player-page table IDs implemented by `F4E-008`:

- `per_game_stats_post`
- `totals_stats_post`
- `per_minute_stats_post`
- `per_poss_post`
- `advanced_post`
- `shooting_post`
- `adj_shooting_post`
- `pbp_stats_post`

## Postseason Stats

Postseason stats are a separate `stats` table family. They must not be mixed
into regular-season `player_season_*` or `player_team_season_*` tables.

Planned postseason player-season tables:

- `stats.player_postseason_totals`
- `stats.player_postseason_per_game`
- `stats.player_postseason_per_minute`
- `stats.player_postseason_per_poss`
- `stats.player_postseason_advanced`
- `stats.player_postseason_shooting`
- `stats.player_postseason_adj_shooting`
- `stats.player_postseason_pbp`

Planned postseason team-stint tables:

- `stats.player_team_postseason_totals`
- `stats.player_team_postseason_per_game`
- `stats.player_team_postseason_per_minute`
- `stats.player_team_postseason_per_poss`
- `stats.player_team_postseason_advanced`
- `stats.player_team_postseason_shooting`
- `stats.player_team_postseason_adj_shooting`
- `stats.player_team_postseason_pbp`

Default FK plan:

- `stats.player_postseason_*` FKs to `core.player_seasons.id`.
- `stats.player_team_postseason_*` FKs to `core.player_team_seasons.id`.

Do not create new `core` postseason tables unless a later reviewed design
proves the existing season and team-stint grains are insufficient.

## Downstream Task Contracts

F4E-002 implements this document as additive SQLAlchemy 2.0 models in
`src/nba_data/db/models/stats.py` and an Alembic revision after
`0002_core_team_player_season`.

F4E-003 repositories:

- perform idempotent insert/update by each table's FK grain;
- do not call `session.commit()` or `session.rollback()`;
- do not create `core` rows;
- fail or report missing FKs before inserting stats rows.

F4E-004 loader:

- starts from parsed, normalized, and validated rows;
- resolves team-stint rows to `core.player_team_seasons.id`;
- resolves player-page full-season rows to `core.player_seasons.id`;
- routes every supported `source_table`;
- reports skipped/quarantined rows for missing FKs or unsupported keys.

F4E-005 backfill:

- is offline/cache-only;
- uses existing cached HTML and does not contact Basketball Reference;
- requires a guarded command such as:

```bash
uv run nba-data backfill stats --execute-approved-stats-backfill --output reports/stats-backfill-2000-2025.json
```

- may support `--limit`, `--team`, `--start-year`, `--end-year`, and
  `--max-workers`;
- does not reload `core` unless a later reviewed task explicitly decides it.

F4E-006 and F4E-009 validation checks:

- table counts;
- duplicate rows;
- orphan FKs;
- synthetic source-code separation;
- `source_team_code` metadata requirements;
- principal stat population;
- coverage by season and team;
- Basketball Reference numeric ranges;
- regular-season versus postseason separation;
- idempotency;
- absence of generated metrics in `stats`.
