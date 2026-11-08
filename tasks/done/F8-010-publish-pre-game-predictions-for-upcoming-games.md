---
id: F8-010
title: Publish pre-game predictions for upcoming games
track: data
areas:
  - ml
  - database-schema
  - testing
  - documentation
priority: 86
depends_on:
  - F8-007
  - F8-014
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/ml/TEAM_PREDICTOR_EVALUATION.md
  - docs/architecture/SYSTEM_DESIGN.md
  - docs/architecture/IMPACT_MAP.md
  - docs/validation/MIGRATION_HEAD_HANDOVER.md
  - src/nba_data/ml/artifact.py
  - src/nba_data/ml/models.py
  - src/nba_data/ml/team_features.py
  - src/nba_data/db/models/core.py
  - tests/integration/test_game_schema_postgres.py
validation:
  - uv run pytest tests/unit/test_ml_db_models.py tests/unit/test_ml_register.py tests/unit/test_ml_predict.py tests/unit/test_cli_ml.py tests/unit/test_impact_map_documentation.py tests/unit/test_migration_snapshots.py tests/unit/test_ml_dependency_boundary.py
  - uv run pytest tests/integration/test_ml_schema_postgres.py tests/integration/test_ml_predict_postgres.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - bash scripts/validate_database.sh
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Applying the ml revision to the persistent nba database — only from merged origin/main and with the owner's approval.
  - Registering the model and writing predictions into the persistent nba database — the owner's direct instruction per run, like any write to real data.
---

# Goal

Store the model F8-007 selects and the forecasts it makes for scheduled games,
so the API can serve them (`F6-021`) by reading rows. This is the data half of
the plan's Stage 5.

# Evidence and current state

- F8-007 saves the selected model as `data/models/<model>-team-pregame-v1-<sha12>/`
  (`model.joblib`, `metadata.json`) behind one `predict_proba` interface, with
  a hash-checked loader (`ml/artifact.py`), and records whether Stage 5 is a go.
- F8-014 loads 2027 games as `scheduled`; F8-008 keeps them current.
- No `ml` schema exists. The API has no numerical dependency, and WF-009's
  boundary test keeps it that way.

# Human decisions or resources

- [x] **Predictions are computed here, not in the API** (decided 2026-10-18):
      the API stays read-only and free of scikit-learn; the forecast served is
      byte-for-byte the one logged; the cutoff is fixed when the row is
      written; the "unavailable" reason is decided once, by the code that knows
      the features.
- [x] **Tables** (new `ml` schema, one revision):
      `ml.model_versions` — `id`, `name` (unique), `model_family`,
      `feature_definition_version`, `training_seasons` (int array),
      `configuration` and `metrics` (JSONB), `artifact_sha256` (64 hex, unique),
      `is_active`, `registered_at`, with a partial unique index on `is_active`
      where true, so at most one model is active;
      `ml.predictions` — `id`, `game_id` FK `core.games`, `model_version_id` FK,
      `cutoff_date`, `status` in (`available`, `unavailable`),
      `unavailable_reason` in (`team_season_missing`, `insufficient_history`,
      `game_not_scheduled`), `home_win_probability` and
      `away_win_probability` `numeric(7,6)` with a check that they sum to
      exactly 1, `favorite` in (`home`, `away`) or null exactly at 0.5,
      `availability_included` (false until Stage 4 is served), `inputs` JSONB,
      `created_at`. Unique `(game_id, model_version_id, cutoff_date)`.
      Probabilities and favorite are null and the reason is set exactly when
      `status = 'unavailable'`.
- [x] **The served forecast** is the active model's row with the latest
      `cutoff_date` for the game. Old rows are kept, never updated.
- [x] **Cutoff**: `cutoff_date = min(game_date − 2 days, latest date whose
      games are all final in core.games)`; features use history dated
      `<= cutoff_date`, the same horizon F8-007 evaluated.
- [x] **Unavailable** (fixed reasons, never a 50–50): a team-season missing;
      fewer than 5 prior games this season for either team (the shortest
      window); the game not `scheduled`.
- [x] **Rounding**: the model's home probability is rounded half-even to six
      decimals; away = 1 − home, so the sum check holds exactly.
- [x] **Commands**: `nba-data ml register-model <artifact dir> [--activate]`
      verifies the hash and writes `ml.model_versions` (idempotent by hash;
      `--activate` moves the single active flag in one transaction).
      `nba-data ml predict --from YYYY-MM-DD --to YYYY-MM-DD` writes one row per
      scheduled game in the window for the active model; idempotent per
      `(game, model, cutoff)`. Artifacts stay under `data/models/`, never
      committed.
- [x] **No historical backfill of predictions.** Past performance is F8-007's
      report; this table holds forecasts actually issued.
- [x] **No `features.*` tables yet**: inputs are stored per prediction as JSONB.

# Acceptance criteria

- Models in `src/nba_data/db/models/ml.py` and one revision chained on the head
  at the time of writing; `alembic check` clean; `downgrade -1` →
  `upgrade head` round-trips and removes the schema.
- `tests/integration/test_ml_schema_postgres.py` proves by named constraint: the
  sum check, the favorite rule, nulls for `unavailable`, the reason set, the
  single-active index, and the unique key.
- `ml predict` on a disposable database seeded with games and a fixture
  artifact: a team with enough history gets `available` with probabilities equal
  to the model's rounded output; one with 4 prior games gets
  `insufficient_history`; a `final` game gets `game_not_scheduled`; a rerun
  writes nothing; a new day with a later cutoff writes a new row.
- Leakage test: adding a result dated after the cutoff does not change a
  prediction written for that cutoff.
- `register-model` refuses a hash mismatch and a feature-definition version the
  code does not know.
- `IMPACT_MAP.md` counts the `ml` schema; `SYSTEM_DESIGN.md` describes it.

# Scope

`src/nba_data/db/models/ml.py` and `__init__.py`, one revision,
`src/nba_data/ml/` (`register.py`, `predict.py`), `cli/main.py`, the unit and
integration tests above, `docs/architecture/SYSTEM_DESIGN.md`,
`docs/architecture/IMPACT_MAP.md`, `docs/ml/PREDICTOR_PLAN.md`.

# Out of scope

The API route (F6-021). Training and evaluation (F8-007). Player-aware models.
A scheduler.

# Impact

- New `ml` schema and revision; two `ml` commands.
- **API readiness**: after the revision reaches `nba`, the `app` worktree
  answers 503 until its next task starts from the new `origin/main` (ADR 0018).

# Cross-track impact

- Additive: `ml.model_versions` and `ml.predictions` for the `app` track's
  prediction route. The handoff card is `F6-021`; record its `## Open` line in
  `tasks/CROSS_TRACK.md` before this card moves to review.

# Implementation notes

- Start only if F8-007 recorded a go for Stage 5.
- The API's readiness list gains the two tables in `F6-021`, not here.
- The first real publication follows a fresh refresh (F8-008), on the owner's
  instruction.

# Durable knowledge updates

- `docs/ml/PREDICTOR_PLAN.md` — Stage 5 data path.
- `docs/architecture/SYSTEM_DESIGN.md` — the `ml` schema.

# Review evidence

## Automated validation

Run 2026-11-08 on `feature/F8-010-publish-pregame-predictions`.

| Command | Result |
|---|---|
| The seven focused unit modules from `validation:` | 91 passed |
| `uv run ruff check .` | All checks passed |
| `uv run mypy src/nba_data` | No issues in 114 files |
| `uv run pytest` | 1879 passed, 295 skipped (the integration lane, run below) |
| `bash scripts/validate_database.sh` | Passed: 296 integration tests, `alembic check` clean, and the `0012` downgrade restored `0011` exactly, `ml` included |
| `uv run python scripts/validate_tasks.py` | Passed after the move to review |

The two integration modules from `validation:` ran inside that database lane,
not on their own: they skip without a disposable database.

The real artifact `logistic-team-pregame-v1-f369530d6c6e` passes its hash check
and holds every metadata key registration needs (loaded read-only). It was not
registered anywhere. No acquisition ran, and `nba` was not touched.

## Manual happy path

On a disposable database whose name starts with `nba_test`, at the head revision:

1. Load games with `DATABASE_URL` pointing at it, including at least five final
   games per team before a `scheduled` game.
2. `uv run nba-data ml register-model data/models/logistic-team-pregame-v1-f369530d6c6e --activate`
3. `uv run nba-data ml predict --from <date> --to <date>`, then run it again.

Expected result: step 2 reports `created: true, is_active: true`. The first
predict writes one row per game, `available` with probabilities summing to 1.
The rerun reports `written: 0`.

## Manual sad path

1. Append a byte to `model.joblib` in a copy of the artifact and register the copy.
2. Run `ml predict` with no active model, or over a window with no games.
3. Run either command with `DATABASE_URL` naming `nba` from this branch.

Expected result: each exits 1 with the reason and writes nothing. Step 3 is
refused by the load-target guard before an engine exists, so it is safe to try.

## Review fixes (2026-11-08)

A code review found five gaps; all are fixed with tests, with no schema change.

1. **Status changes.** A game no longer `scheduled` gets a row only if this model
   has none, so an issued forecast is never buried. A postponed game keeps its
   rows and is listed in `postponed_with_forecast`; `F6-021` now answers it as
   unavailable from `core.games.status`.
2. **Venues.** Publication resolves a NULL `neutral_site` from arena names, for
   targets and Elo history, without writing to `core`. An unknown target venue is
   withheld; unresolved history is counted in `history_venues_unresolved`.
3. **Eligibility.** An unclassified game is forecast only on its home team's floor
   and within each team's 82 games. Others get no row and are named in `withheld`.
4. **Activation.** `ml predict --model NAME` prepares an inactive model, and
   `ml activate NAME` (new) switches. Activation, including
   `register-model --activate`, refuses while a scheduled game the current model
   covers has no `available` forecast from the new one.
5. **History quality.** Each team's last five known games must all have every
   statistic, or the game gets `insufficient_history`. `inputs` records
   `complete_recent_games_home` and `_away`; the report counts
   `blocked_by_blank_statistics`.

## Known limitations

- **Neutral-floor regular-season games are withheld.** Nothing distinguishes the
  Cup final from another neutral game before it is played, so Mexico City, Paris,
  and Cup semifinal games get no forecast either (404 on the route, named in the
  report). Marking the Cup final at load would release them.
- **A postponed game's forecast relies on `F6-021`.** The `available` row stays
  stored, because the card fixes the key and forbids updates. The route must apply
  the status rule added to its card.
- **`team_season_missing` is never written.** `core.games` requires both team
  seasons by foreign key, so the case cannot arise. The value stays in the check
  set the card fixed.
- **Stale games hold the cutoff.** A game left `scheduled` after its date stops
  the cutoff there until a refresh finishes it, by design.

Changes outside the card's stated scope, each required by it: `alembic/env.py`
and `scripts/validate_postgres_local.py` (include `ml`);
`tests/unit/test_team_pregame_features.py` (its "only `team_games.py` touches the
database" rule now also exempts `register.py` and `predict.py`, which the card
places in `ml/`). Both `ml` commands also run `require_load_target`, which the
card did not name, so they refuse `nba` unless on clean merged code.
