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

- New read-only `nba_data.ml` package. `WF-009`'s boundary test will keep `nba_data.api` from importing it.

# Cross-track impact

- None.

# Implementation notes

- Keep records frozen dataclasses so a test can mutate copies safely.
- Order history by `(game_date, basketball_reference_game_id)`; the id breaks
  ties deterministically.
- **Neutral encoding** (owner, 2026-10-29): a neutral game means neither team
  is at home, as the Elo decision above already does; the rule does not change.
  The build must report how many `NULL` `neutral_site` values it treated as
  home. For 2015–2026 the expected count is 0 once F8-018 has loaded `nba`
  (F8-016 decides the four seasons that are still `NULL` on F8-006's disposable
  copy).
- **Quarantined games** (owner, 2026-10-29): the 7 source-error games of
  F8-006 stay out of `core.games`, and this card reads its schedule features
  from `core.games` only. Accepted known limitation, for both teams of each
  omitted game: rest days before the next retained game can be overestimated
  (subject to the cap of 7) and a back-to-back can be hidden; seven-day counts
  can be understated for several later games while the omitted game is inside
  the window; Elo skips the 7 games, which affects later ratings too. Do not
  read schedules from the cache to work around it. Record this under the
  card's known limitations.

# Durable knowledge updates

- `docs/ml/PREDICTOR_PLAN.md` — a "Feature definition `team-pregame-v1`"
  subsection with the formulas and constants above.

# Review evidence

Second review completed on 2026-10-30: no blocking findings remain. The owner
authorized moving this card to done, committing, and pushing after this review.

## Automated validation

- `uv run pytest tests/unit/test_elo.py tests/unit/test_team_pregame_features.py tests/unit/test_team_game_history_query.py`
  — 46 passed (after the review fixes: no autoflush on a dirty Session,
  postponed and unclassified targets refused, input-wide skip counts pinned).
- `uv run pytest tests/integration/test_team_game_history_postgres.py` — 3
  skipped without the disposable-database opt-in, as designed; they run in the
  lane below.
- `uv run ruff check .` — all checks passed (new files also `ruff format`ted).
- `uv run mypy src/nba_data` — no issues in 98 source files.
- `uv run pytest` — 1521 passed, 257 skipped (the integration lane).
- `bash scripts/validate_database.sh` — 258 passed against
  `nba_test_tmp_4c799e50a7a344cf`, including all three
  `test_team_game_history_postgres.py` tests; database dropped.
- `uv run python scripts/validate_tasks.py` — passed.
- Read-only probe against the disposable F8-006 copy `nba_f8006_tmp` (not
  `nba`): 14,435 history games, 2015–2026; features for all 14,432
  regular-season targets built in 3.9 s, the read in 0.43 s; `skipped_games`
  all 0; `null_neutral_as_home` = 4,914 — the four seasons F8-016 still has to
  decide, as the owner's note predicted. (Opening the first connection to the
  local container took 130 s on this machine, outside the query.)

## Manual happy path

1. On the disposable copy, run:
   `uv run python -c "from sqlalchemy import create_engine; from sqlalchemy.orm import Session; from nba_data.ml.team_games import load_team_game_history; from nba_data.ml.team_features import build_team_features; g = load_team_game_history(Session(create_engine('postgresql+psycopg://nba:nba@localhost:5432/nba_f8006_tmp'))); b = build_team_features(g, target_ids=[x.game_id for x in g if x.game_type == 'regular_season']); print(len(g), len(b.rows), b.skipped_games, b.null_neutral_as_home); print(b.rows[-1])"`
2. Inspect the last row: Elo values near 1500 ± a few hundred, `is_neutral`
   a bool, 45 `diff_*_l5/_l10/_l20/_season` values plus the schedule
   differences.
3. Pick an opening-night game (`games_in_season_before_home == 0`).

Expected result: 14,435 records, 14,432 rows, all skips 0, 4,914 undetermined
venues; the opening-night row has every results difference and
`diff_rest_days` as `None`, and carried-over Elo values that are not 1500.

## Manual sad path

1. `build_team_features(g, target_ids=["202401010ZZZ"])` → `ValueError`
   "not among the games".
2. Pass a playoff or cup-final game id as a target → `ValueError`
   "only regular-season games are targets"; a postponed game → "postponed";
   a scheduled game with no `game_type` → "no competition type".
3. Pass the same record twice in `games`, or a bare string as `target_ids` →
   `ValueError` "appears twice" / `TypeError`.

Expected result: each call fails loudly; nothing is written anywhere.

## Known limitations

- The 7 games F8-006 quarantined are absent from `core.games`. For both teams
  of each: rest before the next retained game can be overestimated (up to the
  cap of 7) and a back-to-back hidden; seven-day counts can be understated for
  several later games while the omitted game is inside the window; Elo skips
  the 7 games, which affects later ratings too. Accepted by the owner
  (2026-10-29); schedules are not read from the cache to work around it.
- Until F8-016 and F8-018 land, 4,914 games of four seasons have `NULL`
  `neutral_site` and count as home games; the build reports the number.
- "Adding a new later game, or deleting one" is tested for games dated after
  the target. A game between the cutoff and the target legitimately moves the
  schedule features (rest, back-to-back, seven-day count), which read the
  published schedule up to the day before the target by design; its scores and
  counters are tested to change nothing.
- `load_team_game_history` returns history only (final `regular_season` and
  `cup_final`). **F8-010 integration requirement:** `core.games` stores a
  scheduled game with `game_type` `NULL`, and the builder refuses such a target
  ("no competition type"). F8-010 needs a schedule read and a reliable
  competition classification before scheduled games can be targets, and must
  test the stored shape. Unclassified scheduled records still feed schedule
  features.
- `skipped_games` counts cover all supplied history, not one target's history
  up to its cutoff. A later incomplete game changes the counts but not any
  feature value. Per-target coverage is `games_in_season_before_home/_away`.
- Rest days are `(target − previous game) − 1`, so a back-to-back has 0 rest;
  a team's first game of each season has `None` rest (windows reset each
  season).
- `docs/ml/PREDICTOR_PLAN.md` still opens with "Nothing in it is implemented",
  stale since F8-002; left as the owner's status line.

## Second-review validation (2026-10-30)

- Rechecked the happy path, result cutoffs, season transitions, missing counters,
  and target validation. The dirty-Session regression now verifies that reads
  leave pending changes unflushed; postponed targets fail explicitly.
- Focused unit tests: 46 passed. Full suite: 1521 passed, 257 skipped.
- `uv run python scripts/validate_postgres_local.py`: 258 passed against
  `nba_test_tmp_ca95085a6e854b0c`; temporary database dropped. This is the
  Python entry point used by the Bash wrapper, unavailable in this shell.
- Ruff, mypy (98 source files), and `git diff --check` passed.
- No F8-011 cross-track entries or parked-card bookkeeping need closing.
- Scheduled target classification remains an explicit F8-010 integration
  requirement; input-wide skip counts and quarantined games remain documented
  limitations.
