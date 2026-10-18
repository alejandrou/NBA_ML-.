---
id: F6-021
title: Serve the game prediction route
track: app
areas:
  - api
  - database-read
  - testing
priority: 84
depends_on:
  - F6-013
  - F6-020
  - F8-010
read:
  - docs/architecture/API_CONTRACT.md
  - docs/architecture/API_ARCHITECTURE.md
  - docs/ml/PREDICTOR_PLAN.md
  - docs/architecture/SYSTEM_DESIGN.md
  - src/nba_data/db/models/ml.py
  - src/nba_data/api/schemas/common.py
  - src/nba_data/api/routers/games.py
  - src/nba_data/api/services/readiness.py
  - tests/unit/test_game_api.py
validation:
  - uv run pytest tests/unit/test_game_prediction_api.py tests/unit/test_game_prediction_query_repository.py tests/unit/test_api_readiness.py tests/unit/test_api_foundation.py tests/unit/test_ml_dependency_boundary.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest -m "not integration and not live"
  - bash scripts/validate_database.sh
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None. The route reads the database. Real forecasts need F8-010's revision and a prediction run on the persistent nba database, both owner-approved data-track steps outside this card.
---

# Goal

Serve `GET /api/v1/games/{game_id}/prediction`: the stored pre-game forecast
for one game, or an explicit "unavailable" with its reason. This completes the
plan's Stage 5 query.

# Evidence and current state

- The plan's Stage 5 fixes the response content: teams, scheduled start,
  complementary probabilities, favorite, data date, model version, and whether
  player availability is included; missing data yields "forecast unavailable"
  with a reason, never a 50–50 stand-in.
- `F8-010` stores forecasts in `ml.predictions` with both probabilities
  (`numeric(7,6)`, summing to exactly 1), the favorite, the cutoff date, the
  status, the reason (`team_season_missing`, `insufficient_history`,
  `game_not_scheduled`), and `availability_included`; `ml.model_versions`
  holds the model name and the single active flag. The API reads them and
  computes nothing.
- `F6-013` adds `ApiDecimal` (`api/schemas/common.py`), which serializes a
  `Decimal` as a JSON number; this route reuses it.
- `F6-020` serves the game id, teams, and start time this route reuses.

# Human decisions or resources

- [x] **Read, not infer** — decided in `F8-010`: the API runs no model and has
      no ML dependency.
- [x] **Body**: `game_id`, `home` / `away` (team code and abbreviation, as in
      `F6-020`), `game_date`, `start_time_et`, `status` (`available`,
      `unavailable`), `home_win_probability`, `away_win_probability`
      (JSON numbers), `favorite` (`home`, `away`, or `null`), `data_as_of`
      (the cutoff date), `model_version`, `availability_included`, and
      `unavailable_reason` (`null` when available). Probabilities are `null`
      when unavailable. `model_version` is `ml.model_versions.name`; the
      surrogate ids stay private.
- [x] **Status codes**: unknown game → 404 `Game not found`; known game with no
      forecast row (e.g. a past game, or not yet predicted) → 404
      `Prediction not found`; an `unavailable` row → 200 with its reason.
      Strings fixed, never interpolated.
- [x] **Which row**: the active model's row with the latest `cutoff_date`, the
      rule `F8-010` defines.
- [x] **Readiness** adds `ml.model_versions` and `ml.predictions`.

# Acceptance criteria

- `API_CONTRACT.md` gets the route, body, codes, and readiness change first,
  in its `## Games` section.
- `db/repositories/queries/game_predictions.py`: one read-only query joining
  `core.games`, the active `ml.model_versions` row, and its latest-cutoff
  `ml.predictions` row; never mutates the Session.
- Offline `TestClient` tests: available; unavailable with each of the three
  reasons; no row → 404 `Prediction not found`; unknown and malformed game id
  → 404 `Game not found`; two cutoffs (latest wins); an inactive model's newer
  row ignored; no active model → 404 `Prediction not found`; probabilities
  asserted as JSON numbers equal to the stored values (`0.512345` stays
  `0.512345`); `favorite` `null` at 0.5.
- Readiness adds `ml.model_versions` and `ml.predictions`; a missing one → 503
  `Database schema not ready`.
- `tests/integration/test_api_postgres.py` seeds one game, one active model,
  and one prediction on disposable PostgreSQL and reads them through the route.
- If `web/` exists (F7-002), its committed OpenAPI snapshot is refreshed.

# Scope

`src/nba_data/api/` prediction route, schema, and query; tests;
`API_CONTRACT.md`.

# Out of scope

Running a model, writing predictions, prediction history, and the web page
(`F7-005`).

# Impact

- One new route and two readiness tables.

# Cross-track impact

- None.

# Implementation notes

- `numeric(7,6)` is read as `Decimal` and serialized through `ApiDecimal`; do
  not add a second serializer.
- The bodies follow F8-010's merged revision; if a column differs, follow the
  revision and say so in review.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md`.

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
