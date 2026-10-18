---
id: F6-013
title: Serve the regular-season aggregate and stint stat routes
track: app
areas:
  - api
  - database-read
  - testing
  - documentation
priority: 90
depends_on:
  - F6-004
  - F6-012
  - F4E-024
read:
  - docs/architecture/API_CONTRACT.md
  - docs/architecture/API_ARCHITECTURE.md
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
  - src/nba_data/db/models/stats.py
  - src/nba_data/domain/team_codes.py
  - src/nba_data/api/routers/players.py
  - src/nba_data/api/services/players.py
  - src/nba_data/api/schemas/players.py
  - src/nba_data/api/services/readiness.py
  - src/nba_data/db/repositories/queries/players.py
  - tests/unit/test_player_api.py
  - tests/unit/test_api_readiness.py
validation:
  - uv run pytest tests/unit/test_player_stats_api.py tests/unit/test_player_stats_service.py tests/unit/test_player_stats_query_repository.py tests/unit/test_api_readiness.py tests/unit/test_api_foundation.py tests/unit/test_player_api.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest -m "not integration and not live"
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None. The routes read the database; no load, backfill, or rebuild happens here.
---

# Goal

Serve the regular-season half of the two statistics route templates across all
eight families:

```text
GET /api/v1/players/{pid}/seasons/{season_year}/regular/aggregate/{family}
GET /api/v1/players/{pid}/seasons/{season_year}/regular/stints/{family}
```

`stats.player_season_{family}` is the aggregate grain and
`stats.player_team_season_{family}` the stint grain. The family schemas built
here are reused unchanged by F6-014.

# Evidence and current state

- `API_CONTRACT.md` fixes the routing table, the body shape, `is_multi_team`,
  the null and JSON-number rules, the stint ordering
  (`basketball_reference_team_id ASC`), and the status codes.
- All four dimensions inherit the same eight column mixins
  (`src/nba_data/db/models/stats.py`): `_TotalsColumnsMixin`,
  `_PerGameColumnsMixin`, and so on. The mixins also carry `rk`, `age`,
  `position`, `awards`, and `player_name_display`.
- **Data health is settled.** F4E-024 rehearsed the rebuild and F4E-031 applied
  it: the persistent `nba` database is at the `-v4` baseline since 2026-09-05
  (`docs/validation/OFFLINE_DATABASE_PREPARATION.md`): 101,336 regular player
  rows, 12,667 player-seasons, zero rows at `-v1` to `-v3`. The card text that
  called the aggregate family stale and 625 seasons short predates that run.
- Readiness checks one schema: `REQUIRED_SCHEMA = "core"` and bare table names
  (`src/nba_data/api/services/readiness.py:22-29`). It cannot yet name a
  `stats` table.
- `API_ARCHITECTURE.md` confines API reads to `db/repositories/queries/`;
  `StatsRepository` is the write path and is not reused.
- Pydantic serializes `Decimal` to a JSON string by default; no schema in
  `src/nba_data/api/schemas/` handles `Decimal` today.

# Human decisions or resources

- [x] **Dispatch: generated, typed routes.** One map from family to the two ORM
      models and two Pydantic bodies drives a loop that registers one route per
      family and grain, each with its own `response_model`. OpenAPI therefore
      carries a distinct, fully typed body per family, which the web app's
      generated types need (ADR 0019). A single `{family}` route would publish
      an untyped union. After the literal routes, one hidden route
      (`include_in_schema=False`) takes `{season_type}` and `{family}` as enums,
      so an unrecognized value still returns the contract's 422; a valid but
      unserved combination (postseason, until F6-014) returns 404.
- [x] **Staleness does not hide rows.** The API publishes no lineage and filters
      on none; data health is the `data` track's gate
      (`validate official-stats`). The database is at `-v4`, so the question no
      longer blocks shipping.
- [x] **Rates**: one annotated type, `ApiDecimal =
      Annotated[Decimal, PlainSerializer(float, return_type=float,
      when_used="json")]`, in a new `src/nba_data/api/schemas/common.py`, used
      by every `Numeric` column. OpenAPI shows `number`. `0.4660` serializes as
      `0.466`; JSON numbers carry no scale, so the contract's "at their stored
      scale" is corrected to "as the stored value".
- [x] **A stint without a stat row is omitted.** The collection lists stat rows
      only; membership is already served by the season index's `teams`.
      Inventing a row of nulls would assert a stint the stat table does not
      hold.
- [x] **Published columns**: every column of the family's mixin except
      `player_name_display` (a named non-promise), the primary key, the grain
      FK, and lineage. `rk`, `age`, `position`, and `awards` are published
      verbatim, `null` when absent.

# Acceptance criteria

- `src/nba_data/db/repositories/queries/player_stats.py`: read-only queries for
  one aggregate row and one page of stint rows of a family, scoped by player id
  and season year through `core.player_seasons` /
  `core.player_team_seasons`, NBA seasons only, never mutating the Session.
- `src/nba_data/api/schemas/player_stats.py`: one aggregate and one stint body
  per family. A unit test derives each body's stat fields from the mapped
  mixin columns minus the exclusions above and asserts equality, so a new
  stored column fails the test until it is published or excluded.
- `is_multi_team` comes from `team_codes.is_multi_team_marker`; a test pins
  `2TM` and `5TM` as true, a real code as false, and `null` as false.
- Routes as decided above. Status codes exactly per contract: 404
  `Player not found`, 404 `Player season not found`, 404 `Statistics not found`
  for a missing aggregate row, 200 with an empty `items` list for an empty stint
  collection, 422 for an unrecognized `{season_type}` or `{family}`, 422 for a
  non-integer `{season_year}`. `detail` strings are fixed.
- Stint collections use the envelope, `page_size` ≤ 100, ordered by team code.
- Readiness takes schema-qualified names (`core.teams`, `stats.…`) and adds the
  16 regular `stats` tables served here. `test_api_readiness.py` covers a
  missing `stats` table → 503 `Database schema not ready`.
- `TestClient` tests cover: every family on both grains; a `2TM` aggregate with
  its stints; an old season whose newer columns are `null` (not `0`, not
  omitted); a rate asserted as a JSON number; no lineage key and no
  `player_name_display` in any body; the hidden route's 422 and 404.
- `test_api_foundation.py` still passes (every OpenAPI path under `/api/v1/`;
  the hidden route is not in the document).
- `API_CONTRACT.md`: the "Specified, not yet served" marker names only the
  postseason routes; the stale F4E-024 sentence is removed; the published
  column rule, the omitted-stint rule, and the rate wording are recorded.

# Scope

`src/nba_data/api/` (routers, services, schemas),
`src/nba_data/db/repositories/queries/`, `readiness.py`, `tests/unit/`, and
`docs/architecture/API_CONTRACT.md`.

# Out of scope

Postseason routes (F6-014). The roster table. Any write, load, backfill, or
rebuild. Any schema change. Generated metrics. Contacting Basketball Reference.

# Impact

- Sixteen served combinations; readiness becomes multi-schema.

# Cross-track impact

- None.

# Implementation notes

The contract is the authority on what a body contains; `stats.py` on which
columns a family has. Do not restate the collection envelope or the error
taxonomy. Build the family map with both season types' tables named, so F6-014
only registers the postseason entries.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — as listed in the acceptance criteria.

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
