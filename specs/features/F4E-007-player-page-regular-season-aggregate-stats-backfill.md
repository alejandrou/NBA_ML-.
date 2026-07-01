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
- Add `source_team_code` metadata to player-season stat tables.
- Treat `2TM`, `3TM`, and `4TM` as source markers, not teams.
- Do not insert `TOT`, `2TM`, `3TM`, or `4TM` into `core.teams`,
  `core.team_seasons`, or `stats.player_team_season_*`.
- Do not calculate full player-season stats by summing team stints, averaging
  percentages, or deriving advanced metrics.
- Keep parsers pure: HTML in, structured rows out, no network and no database.
- Keep loading idempotent and caller-transaction-owned.

## Acceptance Criteria

- Player-page regular-season source mapping matches
  `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md`.
- Parser/normalizer tests use fixture HTML and make no network requests.
- Loader tests prove `2TM`, `3TM`, and `4TM` route only to
  `stats.player_season_*`.
- Existing team-season `stats.player_team_season_*` behavior remains intact.
- Game Highs and other out-of-scope player-page tables are ignored.
- No live scraping, Basketball Reference contact, API, frontend, generated
  metrics, OVR, rankings, similarity, recommendations, or ML work is added.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live player-page acquisition without exact owner approval.
- Postseason stats; use `F4E-008`.
- Final official stats closure; use `F4E-009`.

