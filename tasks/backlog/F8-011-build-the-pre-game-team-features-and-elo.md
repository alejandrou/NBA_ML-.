---
id: F8-011
title: Build the pre-game team features and Elo
track: data
areas:
  - ml
  - database-read
  - testing
  - documentation
priority: 93
depends_on:
  - F8-002
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/domain/BUSINESS_RULES.md
  - docs/architecture/SYSTEM_DESIGN.md
  - src/nba_data/db/models/core.py
  - src/nba_data/db/models/stats.py
  - tests/integration/conftest.py
validation:
  - uv run pytest tests/unit/test_elo.py tests/unit/test_team_pregame_features.py tests/unit/test_team_game_history_query.py
  - uv run pytest tests/integration/test_team_game_history_postgres.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - bash scripts/validate_database.sh
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None. Read-only queries and pure functions; tests seed a disposable database.
---

# Goal

Turn the loaded games into one leakage-proof row of pre-game team features per
regular-season game, plus an Elo rating, in plain Python with no new
dependency. This is the input of every Stage 3 model (F8-007) and of the
forecasts F8-010 stores.

# Evidence and current state

- After F8-002, a game is `core.games` (date, season, home and away
  team-seasons, `game_type`, `status`, `neutral_site`, `start_time_et`) plus two
  `stats.team_game_totals` rows (`pts`, `seconds_played`, and the 14 other
  counters, nullable).
- `docs/ml/PREDICTOR_PLAN.md` §2 lists the variables: Elo difference, offensive
  and defensive efficiency, pace, margin, the four factors over 5, 10, and 20
  games and season-to-date, rest, back-to-backs, games in seven days, and
  history size.
- Every team code from 2014-15 to 2026-27 is stable (Charlotte is `CHO` and
  New Orleans `NOP` from 2014-15), so `core.teams.basketball_reference_team_id`
  links a team across those seasons without inferring a franchise.
- F8-007's decisions fix the cutoff: results-based features use games dated at
  least two days before the target game; schedule features use the published
  schedule.

# Human decisions or resources

- [x] **Package `src/nba_data/ml/`**: `team_games.py` (read-only query →
      frozen `TeamGameRecord`s), `elo.py`, `team_features.py`. Pure functions
      over records; only `team_games.py` touches the database.
- [x] **History** is every `final` game of type `regular_season` or
      `cup_final`. **Targets** are `regular_season` games only (F8-007).
- [x] **Elo** (FiveThirtyEight form, fixed now, tunable only in F8-007):
      start 1500; K = 20; home advantage 100 points, zeroed when
      `neutral_site` is true (`NULL` counts as home); margin-of-victory
      multiplier `(|margin| + 3)^0.8 / (7.5 + 0.006 · elo_diff_winner)`, where
      `elo_diff_winner` is the winner's pre-game rating minus the loser's,
      home advantage included;
      between seasons a rating keeps 75 % and regresses 25 % to 1505. A team
      code with no earlier game starts at 1500. Ratings are read before the
      game and updated after it, in `(game_date, game_id)` order.
- [x] **Windows reset each season** (5, 10, 20 games and season-to-date). A
      window with fewer games than its size uses the games it has; with none,
      its values are `None`, never `0`. `games_in_season_before` carries the
      history size. Elo is the only cross-season memory.
- [x] **Formulas**: possessions `fga + 0.44·fta − orb + tov` averaged over both
      teams of a game; offensive and defensive rating per 100 possessions;
      pace = possessions per 48 minutes (`seconds_played / 5 / 60`); four
      factors eFG% `(fg + 0.5·fg3) / fga`, TOV% `tov / (fga + 0.44·fta + tov)`,
      ORB% `orb / (orb + opp drb)`, FT rate `ft / fga`. A game with any needed
      counter `NULL` is skipped by that feature and counted in
      `skipped_games`; a zero denominator gives `None`.
- [x] **Schedule features**: rest days (capped at 7; `None` for a team's first
      game), back-to-back, games in the previous seven days, all from the
      schedule including the target date, never from results.
- [x] **Output**: `home − away` differences plus `elo_home`, `elo_away`,
      `is_neutral`, and both history sizes, keyed by game id, with
      `FEATURE_DEFINITION_VERSION = "team-pregame-v1"`. Any change to a
      formula, window, or constant bumps the version.

# Acceptance criteria

- `build_team_features(games, *, target_ids, cutoff=None)` returns one row per
  target game; each row uses only history games with
  `game_date <= target.game_date - 2 days` (or `<= cutoff` when given, if
  earlier) for results-based features.
- **Leakage test** (`test_team_pregame_features.py`): for a fixed target,
  changing the score or counters of any game dated after its cutoff, adding a
  new later game, or deleting one leaves every feature of that target
  byte-for-byte equal; changing a game before the cutoff changes it.
- Elo tests: a hand-computed three-game sequence; neutral-site zeroing; the
  season carry-over; a new code at 1500; replaying the same games twice gives
  identical ratings.
- Window tests: early season (fewer games than the window), a team's first
  game (`None`, not `0`), a `NULL` counter skipped and counted, back-to-back and
  seven-day counts across a month boundary.
- `team_games.py` reads with one `SELECT` and never adds, flushes, or commits;
  `test_team_game_history_postgres.py` seeds two seasons on disposable
  PostgreSQL and asserts the records, including a `cup_final` in history and a
  scheduled game excluded.
- No numpy, pandas, or scikit-learn import in these modules.

# Scope

`src/nba_data/ml/` (new: `__init__.py`, `team_games.py`, `elo.py`,
`team_features.py`); `tests/unit/test_elo.py`, `test_team_pregame_features.py`,
`test_team_game_history_query.py`; `tests/integration/test_team_game_history_postgres.py`;
`docs/ml/PREDICTOR_PLAN.md` (feature definition `team-pregame-v1`).

# Out of scope

Models, evaluation, and reports (F8-007). Player features (F8-009). Any table,
revision, or CLI command. Any write to the database.

# Impact

- New read-only `nba_data.ml` package.

# Cross-track impact

- None. `WF-009`'s boundary test keeps `nba_data.api` from importing it.

# Implementation notes

- Keep records frozen dataclasses so a test can mutate copies safely.
- Order history by `(game_date, basketball_reference_game_id)`; the id breaks
  ties deterministically.

# Durable knowledge updates

- `docs/ml/PREDICTOR_PLAN.md` — a "Feature definition `team-pregame-v1`"
  subsection with the formulas and constants above.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command:
- Result:

## Manual happy path

1.
2.
3.

Expected result:

## Manual sad path

1.
2.
3.

Expected result:

## Known limitations

- None.
