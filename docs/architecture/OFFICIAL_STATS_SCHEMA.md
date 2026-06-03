# Official Stats Schema

## Purpose

This document defines the target storage design for official Basketball
Reference player statistics. It is a design record for Phase 4E and does not
implement SQLAlchemy models, Alembic migrations, loaders, or database writes.

The project keeps a strict schema boundary:

```text
core = identity and relationships
stats = official scraped Basketball Reference statistics
features = app-generated metrics such as OVR, rankings, similarity, recommendations, and ML features
```

## Source Boundary

The initial `stats` scope is NBA team-season pages already supported by the
current parser:

- `roster`
- `totals`
- `per_game`
- `per_minute`
- `per_poss`
- `advanced`
- `shooting`
- `adj_shooting`
- `pbp`

The current normalized row shape provides context fields plus a `values` map.
F4E must convert those official `values` keys into typed relational columns,
not store them as primary `JSONB`.

Before final columns are frozen, F4E-001 must inspect normalized keys emitted
by `normalize_team_season_page(...)` for every supported `source_table`.

## Table Families

`TOT` is not a real team. Official aggregate `TOT` rows are persisted in
player-season aggregate tables and never in real team-stint tables.

Team-stint tables FK to `core.player_team_seasons.id`:

- `stats.player_team_season_roster`
- `stats.player_team_season_totals`
- `stats.player_team_season_per_game`
- `stats.player_team_season_per_minute`
- `stats.player_team_season_per_poss`
- `stats.player_team_season_advanced`
- `stats.player_team_season_shooting`
- `stats.player_team_season_adj_shooting`
- `stats.player_team_season_pbp`

Aggregate tables FK to `core.player_seasons.id`:

- `stats.player_season_totals`
- `stats.player_season_per_game`
- `stats.player_season_per_minute`
- `stats.player_season_per_poss`
- `stats.player_season_advanced`
- `stats.player_season_shooting`
- `stats.player_season_adj_shooting`
- `stats.player_season_pbp`

Each wide table has:

- `id` as a surrogate primary key;
- a non-null FK to its owning `core` grain;
- a unique constraint on that FK;
- typed nullable stat columns.

## Column Typing Rules

- Numeric counts use integers.
- Rates, percentages, per-unit values, plus/minus values, ratings, win shares,
  and advanced values use numeric decimals.
- Official text fields such as awards, college, position, height text, birth
  date text, experience text, display names, and roster flags remain strings
  where needed.
- Stat columns are nullable by default because older seasons may not expose
  every official field and Basketball Reference can leave values blank.
- FK and unique grain columns are non-null.
- `player_name`, `player`, and `name_display` are descriptive only and must
  never be used as stable keys.

## Normalized Keys Observed

The following keys were inspected from the current parser and normalizer using
cached team-season HTML for ATL season end years 2000, 2005, 2010, 2015, 2020,
and 2025. F4E-001 should repeat or broaden this inspection before freezing the
final migration.

`roster`:

```text
birth_date, college, flag, height, number, player, pos, weight, years_experience
```

`totals`:

```text
age, ast, awards, blk, drb, efg_pct, fg, fg2, fg2_pct, fg2a, fg3, fg3_pct,
fg3a, fg_pct, fga, ft, ft_pct, fta, games, games_started, mp, name_display,
orb, pf, pts, ranker, stl, tov, tpl_dbl, trb
```

`per_game`:

```text
age, ast_per_g, awards, blk_per_g, drb_per_g, efg_pct, fg2_pct, fg2_per_g,
fg2a_per_g, fg3_pct, fg3_per_g, fg3a_per_g, fg_pct, fg_per_g, fga_per_g,
ft_pct, ft_per_g, fta_per_g, games, games_started, mp_per_g, name_display,
orb_per_g, pf_per_g, pos, pts_per_g, ranker, stl_per_g, tov_per_g, trb_per_g
```

`per_minute`:

```text
age, ast_per_minute_36, awards, blk_per_minute_36, drb_per_minute_36,
efg_pct, fg2_pct, fg2_per_minute_36, fg2a_per_minute_36, fg3_pct,
fg3_per_minute_36, fg3a_per_minute_36, fg_pct, fg_per_minute_36,
fga_per_minute_36, ft_pct, ft_per_minute_36, fta_per_minute_36, games,
games_started, mp, name_display, orb_per_minute_36, pf_per_minute_36, pos,
pts_per_minute_36, ranker, stl_per_minute_36, tov_per_minute_36,
trb_per_minute_36
```

`per_poss`:

```text
age, ast_per_poss, awards, blk_per_poss, def_rtg, drb_per_poss, efg_pct,
fg2_pct, fg2_per_poss, fg2a_per_poss, fg3_pct, fg3_per_poss, fg3a_per_poss,
fg_pct, fg_per_poss, fga_per_poss, ft_pct, ft_per_poss, fta_per_poss, games,
games_started, mp, name_display, off_rtg, orb_per_poss, pf_per_poss,
pts_per_poss, ranker, stl_per_poss, tov_per_poss, trb_per_poss
```

`advanced`:

```text
age, ast_pct, awards, blk_pct, bpm, dbpm, drb_pct, dws, fg3a_per_fga_pct,
fta_per_fga_pct, games, games_started, mp, name_display, obpm, orb_pct, ows,
per, pos, ranker, stl_pct, tov_pct, trb_pct, ts_pct, usg_pct, vorp, ws,
ws_per_48
```

`shooting`:

```text
age, avg_dist, awards, fg3_heave, fg3a_heave, fg_dunk, fg_pct, fg_pct_00_03,
fg_pct_03_10, fg_pct_10_16, fg_pct_16_xx, fg_pct_corner3, fg_pct_fg2a,
fg_pct_fg3a, games, games_started, mp, name_display, pct_ast_fg2, pct_ast_fg3,
pct_fg3a_corner3, pct_fga_00_03, pct_fga_03_10, pct_fga_10_16,
pct_fga_16_xx, pct_fga_dunk, pct_fga_fg2a, pct_fga_fg3a, pos, ranker
```

`adj_shooting`:

```text
adj_efg_pct, adj_fg2_pct, adj_fg3_pct, adj_fg3a_per_fga_pct, adj_fg_pct,
adj_ft_pct, adj_fta_per_fga_pct, adj_ts_pct, age, awards, efg_pct, fg2_pct,
fg3_pct, fg3a_per_fga_pct, fg_pct, fg_pts_added, ft_pct, fta_per_fga_pct,
games, games_started, mp, name_display, pos, ranker, ts_pct, ts_pts_added
```

`pbp`:

```text
age, and1s, astd_pts, awards, drawn_offensive, drawn_shooting,
fouls_offensive, fouls_shooting, games, games_started, mp, name_display,
own_shots_blk, pct_1, pct_2, pct_3, pct_4, pct_5, plus_minus_net,
plus_minus_on, pos, ranker, tov_bad_pass, tov_lost_ball
```

## Loading Rules

- Load core identity and membership before official stats.
- Real-team rows use `team_context="team"` and
  `stat_scope="player_team_season"`.
- Roster rows use `stat_scope="team_roster"`.
- Aggregate rows use `team_abbreviation="TOT"`,
  `team_context="aggregate"`, and `stat_scope="player_season_aggregate"`.
- Stats loaders reject rows that cannot be matched to a stable
  `basketball_reference_player_id` and the expected `core` grain.
- Reprocessing the same normalized input updates the same stats row and does
  not create duplicates.

