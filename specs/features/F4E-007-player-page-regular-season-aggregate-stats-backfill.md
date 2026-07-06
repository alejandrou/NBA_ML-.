# F4E-007 - Player-Page Regular-Season Aggregate Stats Backfill

## Goal

Plan and implement a cache-only player-page path that populates regular-season
`stats.player_season_*` tables from official Basketball Reference player-page
rows.

## Requirements

- Add player-page parsing for regular-season table IDs:
  `per_game_stats`, `totals_stats`, `per_minute_stats`, `per_poss`,
  `advanced`, `shooting`, `adj_shooting`, and `pbp_stats`.
- Populate matching `stats.player_season_*` tables only.
- For each player-season and supported stat table, load exactly one full-season
  row into `stats.player_season_*`.
- If a synthetic multi-team row `2TM`, `3TM`, or `4TM` exists for that
  player-season, use that row as the `stats.player_season_*` source row.
- If no synthetic multi-team row exists, use the single real-team row for that
  player-season as the `stats.player_season_*` source row.
- For traded seasons, ignore player-page real-team stint rows when loading
  `stats.player_season_*`; those real-team stint rows belong only to
  `stats.player_team_season_*`.
- Add `source_team_code` metadata to player-season stat tables.
- Treat `2TM`, `3TM`, and `4TM` as source markers, not teams.
- Do not insert `TOT`, `2TM`, `3TM`, or `4TM` into `core.teams`,
  `core.team_seasons`, `core.player_team_seasons`, or
  `stats.player_team_season_*`.
- Do not calculate full player-season stats by summing team stints, averaging
  percentages, or deriving advanced metrics.
- Ignore `TOT` and Game Highs for supported Phase 4E player-season stats.
- Keep parsers pure: HTML in, structured rows out, no network and no database.
- Keep loading idempotent and caller-transaction-owned.

Examples:

- James Harden 2020-21:
  `2020-21 2TM` -> `stats.player_season_*`
  `2020-21 HOU` -> team-stint stats only
  `2020-21 BRK` -> team-stint stats only
- Jaylen Brown 2023-24:
  `2023-24 BOS` -> `stats.player_season_*` because there is no synthetic
  multi-team row for that season.

## Acceptance Criteria

- Player-page regular-season source mapping matches
  `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md`.
- Mapping and loader rules document the exact one-row-per-player-season
  selection behavior for single-team and traded seasons.
- Parser/normalizer tests use fixture HTML and make no network requests.
- Loader tests prove `2TM`, `3TM`, and `4TM` route only to
  `stats.player_season_*`.
- Loader tests prove traded-season real-team rows are ignored for
  `stats.player_season_*`.
- Existing team-season `stats.player_team_season_*` behavior remains intact.
- Game Highs and other out-of-scope player-page tables are ignored.
- Planned schema/model work includes adding `source_team_code` to
  `stats.player_season_*` through a later migration/model implementation task.
- No live scraping, Basketball Reference contact, API, frontend, generated
  metrics, OVR, rankings, similarity, recommendations, or ML work is added.

## Planned Implementation Files

The later implementation task is expected to touch:

- `alembic/versions`
- `src/nba_data/db/models/stats.py`
- `src/nba_data/db/repositories/stats.py`
- `src/nba_data/scraping`
- `tests/unit`

This planning pass must not create or modify those runtime files.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live player-page acquisition without exact owner approval.
- Postseason stats; use `F4E-008`.
- Final official stats closure; use `F4E-009`.
