# Current Work

Status: phase_4e_f4e_006_needs_review

## Active Task

- `F4E-006`: Official stats validation checks.
- Status: `needs_review`.
- `F4E-001` is `done` by explicit owner approval of the reviewed schema plan.
- `F4E-002` is `done` by explicit owner approval of the reviewed models,
  Alembic migration, and tests.
- `F4E-003` is `done` by explicit owner approval of the reviewed repositories,
  tests, and validation.
- `F4E-004` is `done` by explicit owner approval of the reviewed normalized-row
  stats loader, tests, and validation.

## Current Phase

- Phase ID: `phase-4e-official-wide-stats-persistence`.
- Phase status: `in_progress`.
- Phase 4E remains pre-API.

## Latest Checkpoint

- Closed `F4E-005` as `done` by explicit owner approval.
- Promoted `F4E-006` through approved work into `needs_review` per the owner
  plan for this checkpoint.
- Added `src/nba_data/validation/official_stats.py` with read-only validation
  over all 17 official `stats` tables plus JSON-safe issue/report dataclasses.
- Added `nba-data validate official-stats` with optional
  `--stats-backfill-report` support, JSON output, and exit code `1` on
  validation failures.
- Added `tests/unit/test_official_stats_validation.py` covering clean pass,
  counts, duplicates, FK/orphan issues, incorrect `TOT` placement, aggregate
  misuse, numeric bounds, generated-metric schema detection, backfill mismatch,
  and CLI behavior.

## Latest Validation

- `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed before
  starting `F4E-006`.
- Focused Ruff check on the official stats validator, CLI, and new tests:
  passed.
- `uv run pytest tests/unit/test_official_stats_validation.py`: passed,
  10 passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 259 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  259 passed, 1 skipped, and 6 Peewee deprecation warnings.

## Guardrails Observed

- The validator is read-only and does not run the stats backfill command,
  create `core` rows, write `stats` rows, own transaction commits or
  rollbacks, run live scraping, refresh cache, or run acquisition.
- No live scraping, Basketball Reference contact, cache refresh, acquisition,
  API/frontend/generated metric work, destructive migration, data deletion,
  Peewee removal, branch creation, or PR occurred.

## Next Safe Action

Review `F4E-006`. Keep Phase 5 pending until Phase 4E closes.

## Documentation Note

- Added reusable Codex execution and context documentation so future prompts
  can reference repository memory instead of repeating long phase context.
- Added `docs/ai/REPO_MAP.md`, `docs/ai/ARCHITECTURE_INVARIANTS.md`, and
  `docs/ai/tasks/README.md` to keep future prompts short and targeted.
- Updated the Codex protocol, usage optimization notes, prompt templates, and
  workflow references to favor compact prompts and minimal file reads.
- Normalized the harness shell scripts to LF to avoid Bash line-ending issues.
