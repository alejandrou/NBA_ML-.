# F4E-009 - Official Stats Final Validation And DB Closure

## Goal

Close Phase 4E only after official stats validation covers regular-season
team-stint stats, player-page full-season stats, postseason stats when added,
synthetic source-code placement, and Basketball Reference numeric ranges.

## Requirements

- Confirm `core.teams` and `core.team_seasons` contain no `TOT`, `2TM`, `3TM`,
  or `4TM`.
- Confirm `stats.player_team_season_*` and
  `stats.player_team_postseason_*` contain no synthetic team codes.
- Confirm `stats.player_season_*` may contain `source_team_code` values such
  as real team codes, `2TM`, `3TM`, or `4TM`.
- Confirm Game Highs and other unsupported player-page tables are not persisted
  as official season stats.
- Correct numeric validation ranges:
  `fg_pct`, `fg2_pct`, `fg3_pct`, and `ft_pct` normally `0-1`;
  `efg_pct` and `ts_pct` conservatively `0-2`;
  advanced and PBP position percentages `0-100`;
  adjusted shooting index columns `0-300`.
- Confirm generated metrics remain absent from `stats`.
- Record final validation, remaining risks, and Phase 4E closure notes.

## Acceptance Criteria

- Validator tests cover synthetic-team-code placement and corrected numeric
  ranges.
- Validator covers all regular-season and postseason Phase 4E table families.
- Validation reports actionable failures for duplicates, orphan FKs, invalid
  core grains, unsupported source rows, and generated-metric contamination.
- Phase 4E docs, progress, review notes, task board, and learning changelog are
  updated for closure readiness.
- Phase 5 remains pending until Phase 4E closure is explicitly approved.
- Owner-accepted `F4E-007` and `F4E-008` remain closed unless a hard blocker is
  found.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference contact.
- Cache refresh or acquisition.
- API endpoints, frontend, generated metrics, OVR, rankings, similarity,
  recommendations, or ML work.
