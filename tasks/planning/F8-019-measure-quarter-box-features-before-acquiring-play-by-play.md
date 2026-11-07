---
id: F8-019
title: Measure quarter-box features before acquiring play-by-play
track: data
areas:
  - planning
  - ml
  - scraping
  - data-quality
  - database-read
  - testing
  - documentation
priority: 79
depends_on:
  - F8-009
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/ml/TEAM_PREDICTOR_EVALUATION.md
  - docs/validation/PER_GAME_ACQUISITION_PILOT.md
  - src/nba_data/scraping/parsers/box_score.py
  - src/nba_data/scraping/cache.py
  - src/nba_data/ml/evaluation.py
  - src/nba_data/ml/team_features.py
  - src/nba_data/ml/team_games.py
validation: []
critical_actions:
  - None. Offline features and evaluation over cached pages and the loaded games; no acquisition, no migration, no database write.
---

# Goal

If F8-009 records a no-go, give play-by-play a second, free test before Stage 4
closes: measure a blowout-free rating and a quarter-level regularized impact,
both built from quarter boxes already cached. The result decides whether F8-015
acquires anything.

# Evidence and current state

- F8-009 measures box-score player variables. Alone, its no-go would delete
  F8-015 with play-by-play's two main claims untested: ratings free of garbage
  time, and impact adjusted for teammates and opponents.
- The rule leaves little room: Logistic beat Elo by 0.0091 of log loss on 2025,
  and its interval's upper end was only −0.0025
  (`docs/ml/TEAM_PREDICTOR_EVALUATION.md`).
- All 14,452 cached box scores have the four quarter boxes for both teams, with
  per-player minutes and team counters. Period points reach the final in 14,431
  games, 117,329 of 117,430 team-periods have complete minutes, and period boxes
  leave out team turnovers. Record:
  `docs/validation/PER_GAME_ACQUISITION_PILOT.md`.
- The margin after three quarters is at least 20 in 15.8 % of cached games.
- `parsers/box_score.py:225` reads only each period's points. Period player
  lines are not parsed, and they are not in the database.
- A full parse costs about 0.24 s per page: 219 s on 16 processes.

# Human decisions or resources

All decisions are taken; the card waits on F8-009's measurement, not on the
owner.

- [x] **Runs only after a no-go** (decided 2026-11-06, before any result): if
      F8-009 records a go, F8-015 starts and this card is deleted unrun.
- [x] **Features** (`team-quarter-pregame-v1` = `team-pregame-v1` plus five
      values, `home − away` as in F8-011):
      **blowout-free net rating** over 5, 10, 20 games and season-to-date, and
      **quarter impact** of the expected rotation.
- [x] **Blowout rule**: when the absolute margin after three quarters is at
      least 20, that game's fourth quarter leaves both points and possessions.
      Kept possessions are the game's less the fourth quarter's, by F8-011's
      formula. Windows, resets, and blanks follow F8-011.
- [x] **Quarter impact**: one weighted ridge fit per Monday. A row is one period
      of one game; the target is home minus away points per 100 possessions,
      weighted by possessions; each column is one player, `+share` at home and
      `−share` away, where `share` is their seconds over the period's length;
      a fitted intercept is home court. Rows are periods dated on or before the
      fit date in that season and the two before it, leaving out neutral sites.
      The penalty is 2,000, fixed before any result, with no search. A target
      uses the latest fit dated on or before its cutoff; `None` if there is
      none. The team value is the rotation's mean impact weighted by F8-009's
      expected minutes; a player absent from the fit counts 0.
- [x] **Cutoff** identical to F8-007: only games dated at least two days before
      the target; the target game's own periods are never used.
- [x] **Data rules, failing closed**: a history game without its four quarter
      boxes stops the build. A period whose team seconds miss five times its
      length by more than 5 s leaves the impact fit and is counted, and more
      than 1 % of periods left out stops the build (measured 0.09 %). A blank
      cell stays blank, never 0.
- [x] **Comparison**: as F8-009, the selected team model's family refitted with
      the new set against the team model on 2025 by F8-007's rule, on identical
      game ids. The 2026 test season is scored once for the record.
- [x] **Go/no-go, fixed now**: F8-015 starts only if `team-quarter-pregame-v1`
      is selected over `team-pregame-v1` on 2025 (its 95 % block-bootstrap
      interval of the log-loss difference lies entirely below 0). Otherwise
      Stage 4 stops, F8-015 is deleted, and the result is recorded.
- [x] **One feature set, one comparison**: rating and impact are not tested
      apart, which would add looks at 2025. This card and F8-009 already raise
      the chance of a false go from about 2.5 % to about 5 %; accepted, because
      that costs an acquisition, not a wrong model.
- [x] **No schema**: period lines stay in the cached pages. Keeping them in
      `stats` is a later card, only if a model that uses them is served.
- [x] **The served model does not change here. Injuries stay out.**

# Acceptance criteria

- A separate, pure reader in `parsers/box_score.py` returns each team's player
  and team lines per period. `parse_box_score_page` and the game loader's
  results do not change.
- `src/nba_data/ml/quarter_games.py` (reads cached pages offline) and
  `quarter_features.py` (pure); `ml evaluate --feature-set` accepts
  `team-quarter-pregame-v1`; the two earlier sets stay byte-identical.
- Leakage test: changing any period of a game after the cutoff, or of the target
  game, leaves every quarter feature of the target unchanged.
- Tests: margin 19 keeps the fourth quarter and 20 drops it; a blank period cell
  is not 0; a game without quarter boxes stops the build; a period with wrong
  minutes is left out and counted; more than 1 % left out stops the build; a
  player absent from the fit counts 0; a neutral game is not in the fit; a
  cutoff on a Monday uses that Monday's fit and one on the Sunday before does
  not; a season's first game gives `None`, not `0`.
- The report compares both sets on identical game ids and states the go/no-go
  for F8-015 by the rule above, with periods left out and an input fingerprint
  covering the extracted rows. `TEAM_PREDICTOR_EVALUATION.md` and
  `PREDICTOR_PLAN.md` Stage 4 record it, dated.

# Scope

`src/nba_data/scraping/parsers/box_score.py` (one added reader),
`src/nba_data/ml/` (two new modules; `evaluation.py` and `cli/main.py` for the
feature-set option), their tests, `docs/ml/`.

# Out of scope

Any acquisition, table, or revision. Play-by-play (F8-015). Tuning the penalty,
the blowout margin, or the fit span. Availability and injuries. Promoting a
model to serving.

# Impact

- A third feature set in the harness and a period-line reader that F8-015 can
  reuse.

# Cross-track impact

- None.

# Implementation notes

- `Prepare F8-019 for implementation.` runs once F8-009 records a no-go. It
  moves this card to the backlog and sets `validation:` to:
  `uv run pytest tests/unit/test_box_score_period_lines.py tests/unit/test_quarter_pregame_features.py tests/unit/test_ml_evaluation.py tests/unit/test_ml_dependency_boundary.py`,
  `uv run ruff check .`, `uv run mypy src/nba_data`, `uv run pytest`,
  `uv run nba-data ml evaluate --feature-set team-quarter-pregame-v1 --output reports/ml/f8-019/evaluation.json --artifact-dir data/models`,
  and `uv run python scripts/validate_tasks.py`.
- Reuse F8-009's expected minutes and rotation. Keep the period reader apart from
  `parse_box_score_page`, so the loader cannot change and pays no extra parse.
- Read pages with a process pool; a sequential parse takes about an hour.
- Period boxes leave out team turnovers, so a fourth quarter's possessions run
  about a fifth of a possession low. Accepted: it changes no rule above.
- Scikit-learn's `Ridge` stays inside `nba_data.ml`;
  `test_ml_dependency_boundary.py` keeps the API clear of it.
- The 7 quarantined games stay absent, with `team-pregame-v1`'s known limitation.

# Durable knowledge updates

- `docs/ml/PREDICTOR_PLAN.md` — the Stage 4 quarter-box result, dated.
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
