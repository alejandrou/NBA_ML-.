# F4E-008 - Postseason Stats Schema And Player-Page Backfill

## Goal

Plan and implement separate postseason `stats` table families populated from
official Basketball Reference player-page postseason rows.

## Requirements

- Add postseason aggregate tables:
  `stats.player_postseason_totals`,
  `stats.player_postseason_per_game`,
  `stats.player_postseason_per_minute`,
  `stats.player_postseason_per_poss`,
  `stats.player_postseason_advanced`,
  `stats.player_postseason_shooting`,
  `stats.player_postseason_adj_shooting`, and
  `stats.player_postseason_pbp`.
- Add postseason team-stint tables:
  `stats.player_team_postseason_totals`,
  `stats.player_team_postseason_per_game`,
  `stats.player_team_postseason_per_minute`,
  `stats.player_team_postseason_per_poss`,
  `stats.player_team_postseason_advanced`,
  `stats.player_team_postseason_shooting`,
  `stats.player_team_postseason_adj_shooting`, and
  `stats.player_team_postseason_pbp`.
- FK `stats.player_postseason_*` to `core.player_seasons.id`.
- FK `stats.player_team_postseason_*` to `core.player_team_seasons.id`.
- Parse postseason player-page table IDs:
  `per_game_stats_post`, `totals_stats_post`, `per_minute_stats_post`,
  `per_poss_post`, `advanced_post`, `shooting_post`, `adj_shooting_post`, and
  `pbp_stats_post`.
- Keep regular-season and postseason stats separate.
- Do not create new core postseason tables unless a reviewed design proves the
  current core grains are insufficient.

## Acceptance Criteria

- Schema, parser, loader, and validation behavior match
  `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md`.
- Alembic migration is additive and reviewed before application.
- Tests cover postseason table routing, FK grains, idempotency, and no-network
  boundaries.
- Regular-season stats are not modified by postseason loading.
- No Game Highs, game logs, splits, All-Star, college, salary, contract, or
  similarity-score tables are persisted as official season stats.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `uv run alembic upgrade head`
- `uv run alembic check`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live player-page acquisition without exact owner approval.
- API, frontend, generated metrics, OVR, rankings, similarity,
  recommendations, or ML work.

