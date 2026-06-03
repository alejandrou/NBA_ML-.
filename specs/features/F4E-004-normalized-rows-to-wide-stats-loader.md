# F4E-004 - Normalized Rows to Wide Stats Loader

## Goal

Convert validated normalized team-season rows into typed wide `stats` rows
using the approved stats repositories.

## Requirements

- Start from already parsed, normalized, and validated rows.
- Require corresponding `core` identity rows to exist before stats loading.
- Route rows by `source_table`, `team_context`, and `stat_scope`.
- Real-team rows load through `core.player_team_seasons.id`.
- Aggregate `TOT` rows load through `core.player_seasons.id`.
- Roster rows load only to `stats.player_team_season_roster`.
- Convert normalized `values` keys into typed table columns.
- Reject rows with missing stable Basketball Reference player IDs unless a
  later reviewed matching strategy exists.
- Preserve caller-owned transaction behavior and entry-level failure reporting.
- Do not store official stats as primary `JSONB`.

## Acceptance Criteria

- Loader maps every supported `source_table` to the expected wide table.
- Loader routes team-stint and aggregate rows to separate table families.
- Invalid routing fails before database writes for that row or entry.
- Rerunning the same validated rows does not duplicate stats rows.
- Missing core identity rows produce actionable loader failures.
- Tests cover routing, type conversion, idempotency, missing identity rows,
  duplicate input, and `TOT` separation.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference contact.
- Cache refresh or raw HTML acquisition.
- New official source tables beyond current team-season parser support.
- API, frontend, generated metrics, OVR, ranking, similarity, or ML work.

