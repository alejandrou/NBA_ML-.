# Current Work

Status: phase_4e_f4e_009_needs_review

## Active Task

- `F4E-006`: Official stats validation checks is `done` through the final
  `F4E-009` validator pass.
- `F4E-007`: Player-page regular-season aggregate stats backfill is `done` by
  explicit owner decision.
- `F4E-008`: Postseason stats schema and player-page backfill is `done` by
  explicit owner decision.
- `F4E-009`: Official stats final validation and database closure is
  `needs_review`.

## Current Phase

- Phase ID: `phase-4e-official-wide-stats-persistence`.
- Phase status: `review`.
- Phase 4E remains pre-API and Phase 5 stays pending until owner acceptance.

## Latest Checkpoint

- Updated `src/nba_data/validation/official_stats.py` to validate the final
  33-table Phase 4E model across regular-season team-stint tables,
  regular-season aggregate tables, postseason aggregate tables, and
  postseason team-stint tables.
- Added schema checks for required tables, grain columns, unique grain
  constraints, and aggregate `source_team_code` metadata presence.
- Added final synthetic-code validation so `TOT`, `2TM`, `3TM`, and `4TM`
  fail in `core` real-team tables and all team-stint stats tables, while
  `2TM`, `3TM`, and `4TM` remain allowed only as aggregate metadata.
- Added aggregate metadata validation so `source_team_code` rejects `TOT`,
  rejects unknown codes, and allows real team codes plus `2TM`/`3TM`/`4TM`.
- Added regular-season versus postseason lineage checks so postseason parser
  metadata cannot land in regular tables and vice versa.
- Corrected Basketball Reference numeric ranges:
  shooting percentages `0-1`, `efg_pct` and `ts_pct` `0-2`, advanced and PBP
  percentages `0-100`, adjusted shooting percentages `0-300`, and signed
  allowances for BPM, VORP, win shares, plus/minus, and points-added fields.
- Expanded `tests/unit/test_official_stats_validation.py` with final-pass
  coverage for clean Harden/Brown regular-season and postseason fixtures,
  missing tables and columns, orphan and invalid grains, synthetic-code misuse,
  accepted Basketball Reference scales, rejected numeric ranges, season-family
  separation, duplicate grains, and CLI failure output.
- Updated the task board and current phase docs so `F4E-007` and `F4E-008`
  are closed by explicit owner decision, `F4E-006` is closed through
  `F4E-009`, and Phase 4E is ready for owner review.

## Latest Validation

- `uv run pytest tests/unit/test_official_stats_validation.py`: passed, 10 passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 305 passed, 1 skipped, and 6 Peewee deprecation warnings.
- `docker compose up -d postgres`: passed.
- `uv run alembic upgrade head`: passed.
- `uv run alembic check`: passed with no new upgrade operations detected.
- `uv run nba-data validate official-stats`: passed with zero issues. The
  current local PostgreSQL state has loaded regular-season team-stint stats,
  while aggregate player-season and postseason stats tables remain present but
  empty.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  305 passed, 1 skipped, and 6 Peewee deprecation warnings.

## Guardrails Observed

- No live scraping, Basketball Reference contact, cache refresh,
  API/frontend/generated metric work, destructive migration, data deletion,
  Peewee removal, branch creation, commit, push, or PR occurred.

## Next Safe Action

- Owner review of `F4E-009` and Phase 4E closure readiness after validation.
- Keep Phase 5 pending until Phase 4E is explicitly accepted.
