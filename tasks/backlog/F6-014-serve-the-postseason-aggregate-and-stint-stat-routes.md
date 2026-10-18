---
id: F6-014
title: Serve the postseason aggregate and stint stat routes
track: app
areas:
  - api
  - database-read
  - testing
  - documentation
priority: 85
depends_on:
  - F6-013
read:
  - docs/architecture/API_CONTRACT.md
  - docs/domain/BUSINESS_RULES.md
  - src/nba_data/db/models/stats.py
  - src/nba_data/api/routers/players.py
  - src/nba_data/api/schemas/player_stats.py
  - src/nba_data/db/repositories/queries/player_stats.py
  - tests/unit/test_player_stats_api.py
validation:
  - uv run pytest tests/unit/test_player_stats_api.py tests/unit/test_player_stats_service.py tests/unit/test_player_stats_query_repository.py tests/unit/test_api_readiness.py tests/unit/test_api_foundation.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest -m "not integration and not live"
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None. The routes read the database; no load, backfill, or rebuild happens here.
---

# Goal

Complete the statistics contract by serving the postseason half:

```text
GET /api/v1/players/{pid}/seasons/{season_year}/postseason/aggregate/{family}
GET /api/v1/players/{pid}/seasons/{season_year}/postseason/stints/{family}
```

across all eight families — `stats.player_postseason_{family}` and
`stats.player_team_postseason_{family}` — reusing F6-013's family bodies
unchanged. Afterwards the "Specified, not yet served" marker leaves
`API_CONTRACT.md`.

# Evidence and current state

- The postseason tables carry the same eight column mixins as the regular ones,
  so F6-013's bodies serve them with no new shape.
- **Data health is settled.** The persistent `nba` database is at `-v4` since
  2026-09-05 (F4E-031): 42,408 postseason aggregate and 42,408 postseason stint
  rows, 5,301 player-seasons and 5,301 team stints, zero unresolved in-scope
  rows, every row `player-page-postseason-parser-v4`
  (`docs/validation/OFFLINE_DATABASE_PREPARATION.md`). Nine seasons are
  postseason-only by design and correct as loaded.
- Postseason stats never mix with regular ones (`BUSINESS_RULES.md`); the path
  segment keeps that true at the boundary.

# Human decisions or resources

- [x] **No postseason appearance → 404 `Statistics not found`**, the contract's
      one code. The archive is coverage-validated (zero in-scope unresolved
      rows), so a missing row means the player did not appear; a second signal
      would only restate that. The web page renders its empty state.
- [x] **F6-013's dispatch generalizes by design**: its family map already names
      both season types' tables. This card registers the postseason entries
      through the same loop. If it needs a new body shape, that is a defect in
      F6-013 to fix there, not a second schema here.
- [x] **The postseason stint family is complete enough to serve** — the counts
      above, measured by the coverage gate.

# Acceptance criteria

- The postseason literal routes are registered by F6-013's loop, each with the
  family's existing `response_model`; the hidden validation route no longer
  returns 404 for any valid combination.
- No regular route reads a postseason table and vice versa: a test loads the
  same player-season with different regular and postseason values and asserts
  each route returns only its own.
- Readiness adds the 16 postseason `stats` tables.
- `TestClient` tests: both grains for every family; a multi-team postseason
  aggregate; a player-season with no postseason row → 404
  `Statistics not found` on the aggregate and 200 empty on the stints.
- `API_CONTRACT.md`: the "Specified, not yet served" marker is removed.

# Scope

`src/nba_data/api/`, `src/nba_data/db/repositories/queries/player_stats.py`,
`readiness.py`, `tests/unit/`, `docs/architecture/API_CONTRACT.md`.

# Out of scope

The roster table. Any write, load, backfill, or rebuild. Any schema change.
Generated metrics. Career or multi-season aggregation.

# Impact

- The last sixteen combinations; the statistics contract is fully served.

# Cross-track impact

- None.

# Implementation notes

- Do not duplicate the family schemas; extend F6-013's map.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — remove the marker.

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
