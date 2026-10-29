---
id: F8-009
title: Add pre-game player variables to the predictor
track: data
areas:
  - ml
  - database-read
  - testing
  - documentation
priority: 80
depends_on:
  - F8-007
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/ml/TEAM_PREDICTOR_EVALUATION.md
  - docs/domain/BUSINESS_RULES.md
  - src/nba_data/ml/team_features.py
  - src/nba_data/ml/evaluation.py
  - src/nba_data/ml/team_games.py
  - src/nba_data/db/models/stats.py
validation:
  - uv run pytest tests/unit/test_player_pregame_features.py tests/unit/test_player_game_history_query.py tests/unit/test_ml_evaluation.py tests/unit/test_ml_dependency_boundary.py
  - uv run pytest tests/integration/test_player_game_history_postgres.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - uv run nba-data ml evaluate --feature-set team-player-pregame-v1 --output reports/ml/f8-009/evaluation.json --artifact-dir data/models
  - bash scripts/validate_database.sh
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None. Read-only features and evaluation over the loaded per-game lines; no acquisition, no database write.
---

# Goal

Stage 4, step one: add pre-game player variables built from the per-game lines
F8-006 acquired and F8-018 loads into `nba` — expected rotation and minutes,
and individual form weighted by expected minutes — and measure on the same games whether they beat the team
model. The measured result decides whether play-by-play is acquired (F8-015).

# Evidence and current state

- `stats.player_game_totals` holds every line from 2014-15 to 2025-26 with
  participation, starter, seconds, the 15 counters, and plus-minus; inactive
  lines have no stats (F8-002, F8-006, loaded into `nba` by F8-018).
- F8-007's harness, splits, selection rule, and report exist; its selected team
  model and `team-pregame-v1` are the baseline.
- Plan Stage 4: compare team → team + players on the same games; play-by-play
  only after this.

# Human decisions or resources

- [x] **Players first** (decided 2026-10-18); play-by-play is a separate card,
      `F8-015`, gated by this card's measured result.
- [x] **Features** (`team-player-pregame-v1` = `team-pregame-v1` plus):
      per team, the expected minutes of each player = their mean seconds over the
      team's last 10 games before the cutoff in which the player had a line (inactive
      counts as 0); the top 8 by expected minutes form the rotation. Per player,
      form = per-36 `pts + 1.2·trb + 1.5·ast + 2·stl + 2·blk − tov − 0.5·(fga − fg)
      − 0.5·(fta − ft)` over their last 10 played games (any team), and
      plus-minus per 48. Team values: the expected-minutes-weighted means of
      form and plus-minus over the rotation, the rotation's continuity (share
      of its expected minutes from players who also were in the previous game's
      rotation), and the number of rotation players with fewer than 5 played
      games. Home − away differences, as in F8-011.
- [x] **Cutoff** identical to F8-007: lines from games dated at least two days
      before the target; the target game's own lines and minutes are never used.
- [x] **Comparison**: the selected team model's family, refitted with the new
      feature set, against the team model on 2025 by F8-007's selection rule.
      The 2026 test season is scored once for the record.
- [x] **Go/no-go for play-by-play, fixed now**: F8-015 starts only if the
      player feature set is selected over the team set on 2025 (its 95 %
      block-bootstrap interval of the log-loss difference lies entirely below
      0). Otherwise Stage 4 stops after this card and the result is recorded.
- [x] **The served model does not change here.** Promoting the player model to
      `ml.model_versions` is a later card, after F8-010 exists.
- [x] **Injuries stay out**: designed in the plan, not part of Stage 4.

# Acceptance criteria

- `src/nba_data/ml/player_games.py` (read-only query) and
  `player_features.py` (pure); `ml evaluate --feature-set` accepts
  `team-pregame-v1` (default) and `team-player-pregame-v1`.
- Leakage test: changing any line of a game after the cutoff, or of the target
  game, leaves every player feature of the target unchanged.
- Tests: a traded player counts for the new team from their first line there; a
  player with only inactive lines has expected minutes 0; a rotation with fewer
  than 8 players; a team's first game (`None`, not `0`).
- The report compares both feature sets on identical game ids and states the
  go/no-go for F8-015 by the rule above; `TEAM_PREDICTOR_EVALUATION.md` and
  `PREDICTOR_PLAN.md` Stage 4 record it, dated.

# Scope

`src/nba_data/ml/` (two new modules; `evaluation.py` and `cli/main.py` for the
feature-set option), `tests/unit/test_player_*.py`,
`tests/integration/test_player_game_history_postgres.py`, `docs/ml/`.

# Out of scope

Play-by-play (F8-015). Availability and injuries. Promoting a model to serving.
Any table or revision.

# Impact

- A second feature set in the harness.

# Cross-track impact

- None until a player-aware model is served and the prediction response says
  so (`availability_included` stays false).

# Implementation notes

- Reuse F8-011's history ordering and windows; keep player and team features
  in separate modules so `team-pregame-v1` stays byte-identical.

# Durable knowledge updates

- `docs/ml/PREDICTOR_PLAN.md` — the Stage 4 player result, dated.
- `docs/ml/TEAM_PREDICTOR_EVALUATION.md`.

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
