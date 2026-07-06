# Current Work

Status: phase_4e_f4e_009_f4e_010_needs_review

## Active Task

- `F4E-006`: Official stats validation checks is `done` through the final
  `F4E-009` validator pass.
- `F4E-007`: Player-page regular-season aggregate stats backfill is `done` by
  explicit owner decision.
- `F4E-008`: Postseason stats schema and player-page backfill is `done` by
  explicit owner decision.
- `F4E-009`: Official stats final validation and database closure is
  `needs_review`.
- `F4E-010`: Player-page cache acquisition is `needs_review`.

## Current Phase

- Phase ID: `phase-4e-official-wide-stats-persistence`.
- Phase status: `review`.
- Phase 4E remains pre-API and Phase 5 stays pending until owner acceptance.

## Latest Checkpoint

- Added `src/nba_data/scraping/player_page_acquisition.py` with a deterministic
  `core.players` manifest builder, optional `core.player_seasons` year
  filtering, dry-run reporting, guarded acquisition execution, safe cache
  writes, and stop-on-429 or stop-on-failure partial reports.
- Added `nba-data acquisition dry-run-player-pages` and
  `nba-data acquisition acquire-player-pages` to `src/nba_data/cli/main.py`.
- Kept live acquisition sequential, cache-first, and client/cache-only:
  manifest planning uses read-only DB queries, the live client is created only
  after manifest validation, and cache writes refuse to overwrite existing
  files.
- Added `tests/unit/test_player_page_acquisition.py` covering URL building,
  season-filtered manifest selection, dry-run cache hits, acquisition reports,
  CLI guards, CLI report output, rate-limit settings, and the no-DB-write
  boundary.
- Added `specs/features/F4E-010-player-page-cache-acquisition.md` and updated
  Phase 4E task/phase docs so the owner-gated player-page acquisition path is
  in scope without starting Phase 5 or changing the cache-only loaders.
- Fixed player-page stats normalization against real cached Basketball
  Reference player-page HTML: regular-season and postseason parsed rows now
  recognize `year_id` and `team_name_abbr` aliases, and normalization excludes
  `year_id`, `team_name_abbr`, and `comp_name_abbr` from stats payload values.
- Fixed the remaining player-page stats load failures against real cache HTML:
  normalized player-page `totals` and `per_poss` rows now drop `pos` before
  loading because the approved wide stats schema does not persist `position`
  on those table families, while other supported tables still retain `pos`
  where the schema maps it.
- Added focused regression coverage for real-cache player-page column aliases
  in `tests/unit/test_player_page_normalizer.py` and
  `tests/unit/test_offline_player_stats_backfill.py`.

## Latest Validation

- `uv run pytest tests/unit/test_player_page_parser.py
  tests/unit/test_player_page_normalizer.py
  tests/unit/test_offline_player_stats_backfill.py`: passed, 19 passed.
- `uv run pytest tests/unit/test_player_page_stats_loader.py
  tests/unit/test_player_page_normalizer.py
  tests/unit/test_offline_player_stats_backfill.py`: passed, 24 passed.
- `uv run ruff check .`: passed.
- Real-cache reproduction for `zubaciv01` through parse -> normalize -> load:
  `loaded_rows=72`, `failed_rows=0`.
- `uv run pytest`: passed, 318 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `uv run pytest`: passed, 319 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `uv run pytest tests/unit/test_player_page_acquisition.py`: passed, 10 passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 315 passed, 1 skipped, and 6 Peewee deprecation warnings.
- `uv run alembic check`: passed with no new upgrade operations detected.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  315 passed, 1 skipped, and 6 Peewee deprecation warnings.

## Guardrails Observed

- No live scraping, Basketball Reference contact, cache refresh, player-page
  acquisition execution, API/frontend/generated metric work, destructive
  migration, data deletion, Peewee removal, branch creation, commit, push, or
  PR occurred.

## Next Safe Action

- Review `F4E-010`, then re-review `F4E-009` and Phase 4E closure readiness
  after validation.
- Keep Phase 5 pending until Phase 4E is explicitly accepted.
