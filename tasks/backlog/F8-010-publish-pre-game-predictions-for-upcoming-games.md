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
