# F4E-006 - Official Stats Validation Checks

## Goal

Add post-load validation checks proving official wide stats are coherent,
queryable, and separated from generated metrics.

Review status: `done` through `F4E-009`. The initial validator was corrected by
the later `F4E-009` pass for synthetic source-code rules, postseason coverage,
and Basketball Reference numeric ranges.

## Requirements

- Count rows by every `stats` table.
- Detect duplicate logical rows at each FK grain.
- Detect orphaned or invalid FK relationships.
- Confirm `TOT`, `2TM`, `3TM`, and `4TM` do not appear as real teams in
  `core.teams` or `core.team_seasons`.
- Confirm synthetic source codes do not appear in `player_team_season_*`
  tables.
- Confirm real-team rows live only in `player_team_season_*` tables.
- Confirm `player_season_*` may carry `source_team_code` values such as real
  team codes, `2TM`, `3TM`, or `4TM` after the future schema update.
- Check expected row coverage against the offline processing/backfill report
  where counts are known.
- Check nullability and numeric ranges for official stat columns.
- Confirm no generated metrics, OVR, rankings, similarity, recommendations, or
  ML outputs are stored in `stats`.
- Produce a clear validation report with actionable failures.

## Acceptance Criteria

- Validation covers all F4E wide stats tables.
- Validation detects duplicate rows, orphan FKs, and incorrect synthetic-code
  placement.
- Validation catches obvious impossible numeric values using Basketball
  Reference scales.
- Validation distinguishes unavailable nullable official fields from parse or
  load failures when report context is available.
- Tests cover passing and failing checks.
- No API implementation is introduced.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference contact.
- Cache refresh or acquisition.
- Data deletion or destructive migrations.
- API endpoints, frontend, generated metrics, OVR, ranking, similarity,
  recommendations, or ML work.

