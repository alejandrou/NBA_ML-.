---
id: F6-020
title: Serve the games and box-score routes
track: app
areas:
  - api
  - database-read
  - testing
  - documentation
priority: 88
depends_on:
  - F8-002
read:
  - docs/architecture/API_CONTRACT.md
  - docs/architecture/API_ARCHITECTURE.md
  - docs/ml/PREDICTOR_PLAN.md
  - docs/domain/BUSINESS_RULES.md
  - src/nba_data/db/models/core.py
  - src/nba_data/db/models/stats.py
  - src/nba_data/api/services/readiness.py
  - src/nba_data/api/routers/players.py
  - tests/unit/test_player_api.py
  - tests/integration/test_api_postgres.py
validation:
  - uv run pytest tests/unit/test_game_api.py tests/unit/test_game_service.py tests/unit/test_game_query_repository.py tests/unit/test_api_readiness.py tests/unit/test_api_foundation.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest -m "not integration and not live"
  - bash scripts/validate_database.sh
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None. The routes read the database. Serving real games needs F8-006's load and F8-002's revision on the persistent nba database, both owner-approved data-track steps outside this card.
---

# Goal

Serve the game grain F8-002 adds: a filterable games collection, one game with
both teams' totals, and its player lines. This is the first half of the plan's
Stage 5 — "OKC vs Chicago tonight" starts by finding the game — and the
`F6-021` prediction route hangs off the game id served here.

# Evidence and current state

- F8-002 (data, backlog) adds `core.games`, `stats.team_game_totals`, and
  `stats.player_game_totals`. This card is its handoff: F8-002 records the
  `## Open` line in `tasks/CROSS_TRACK.md` when it moves to review.
- F8-006 loads 2014-15 to 2025-26, all `final`. F8-014 adds 2026-27 games as
  `scheduled`, `final`, or `postponed` through the same table; they need no new
  route.
- `API_CONTRACT.md` fixes the envelope, pagination (50, max 100), error codes,
  fixed `detail` strings, readiness required tables, private surrogate ids, no
  lineage columns, and "the API computes nothing".
- Teams are keyed by `basketball_reference_team_id` (a code is an era), seasons
  by `season_year` (NBA only), players by `basketball_reference_player_id`.

# Human decisions or resources

- [x] **Routes**: `GET /api/v1/games`, `GET /api/v1/games/{game_id}`, and
      `GET /api/v1/games/{game_id}/players`. `{game_id}` is the Basketball
      Reference id (`202310240DEN`), matched exactly; a malformed id is a 404,
      like an unknown team code.
- [x] **Collection filters**, all optional and combined with AND: `season`
      (season year), `date_from` / `date_to` (inclusive ISO dates), `team`
      (team code, matching either side), `game_type`, `status` (`scheduled`,
      `final`, `postponed`; any other value → 422). Unknown team or
      season → 200 with an empty page; `date_from > date_to` → 400. Ordering:
      `game_date ASC, start_time_et ASC NULLS LAST, game_id ASC`.
- [x] **Game body**: `game_id`, `season_year`, `game_date`, `start_time_et`
      (`"HH:MM"`, US Eastern as published, or `null`), `game_type`, `status`,
      `neutral_site` (`null` = not determined), `venue`, `attendance`
      (`null` ≠ `0`), and `home` / `away` objects with
      `basketball_reference_team_id`, the season's `team_abbreviation`, and
      `pts`. `pts` is
      `null` for a game with no team totals, never `0`. The collection serves
      the same body.
- [x] **Team totals** live in the single-game body only (`home.totals`,
      `away.totals`: `seconds_played` and the 15 counters, nulls kept). The
      collection stays light.
- [x] **Player lines**: the envelope, one item per line, ordered home first,
      then starters, then `seconds_played DESC NULLS LAST`, then player id.
      Fields: `basketball_reference_player_id`, `full_name`, team code,
      `starter`, `participation`, `participation_reason`, `seconds_played`, the
      15 counters, `plus_minus`. Inactive lines are served; a non-played line
      has every stat `null`.
- [x] **No derived values**: no minutes string, no percentages, no winner field,
      no player sums. A client compares `home.pts` and `away.pts`.
- [x] **Readiness** adds the three game tables when the routes land.

# Acceptance criteria

- `API_CONTRACT.md` gets a `## Games` section with the routes, bodies, filters,
  ordering, status codes (`{"detail": "Game not found"}`), and readiness change,
  written before the code.
- Offline tests on fixtures cover every filter, the 400, empty pages, a game
  without totals (`pts` null), attendance `null` vs `0`, `neutral_site` `null`,
  a non-played line with all nulls, and the line ordering.
- `tests/integration/test_api_postgres.py` seeds one final game with both team
  totals and player lines on disposable PostgreSQL and reads it through all
  three routes, including the composite-FK-backed team ids.
- If `web/` exists by then (F7-002), its committed OpenAPI snapshot is
  refreshed.

# Scope

`src/nba_data/api/` (routes, schemas, queries for games), its tests,
`docs/architecture/API_CONTRACT.md`.

# Out of scope

Predictions (`F6-021`), play-by-play, per-period scores, schedule versions,
team or player game logs (`/teams/{code}/games`), and any web page (`F7-005`).

# Impact

- Three new routes and the readiness required-table list.

# Cross-track impact

- None.

# Implementation notes

- The bodies follow F8-002's acceptance criteria; read the merged revision
  first and, if a column differs, follow the revision and say so in review.
- Readiness becomes schema-qualified in F6-013 (priority 90). If F6-013 has not
  landed when this card starts, this card makes that change instead.
- Unit tests seed `core.games` and the two `stats` tables on SQLite like the
  existing query tests; the PostgreSQL-only checks are F8-002's concern.
- The abbreviation comes from `core.team_seasons` of the game's season, so a
  relocated or renamed team shows the one it played under. `core.team_seasons`
  stores no name; names live in `core.team_aliases`, which v1 does not serve.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — the games section.

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
