# Current Work

Status: phase_4b_f4b_003_needs_review

## Active Task

- `F4B-002` is `done` after review approval and validation.
- `F4B-003` is `needs_review`.
- No task is currently `approved` or `in_progress`.

## Current Phase

- Phase ID: `phase-4b-controlled-raw-html-backfill`
- Phase status: `proposed`
- `F4B-001` and `F4B-002` are `done`.
- `F4B-003` is `needs_review`.
- `F4B-LIVE-001` remains `pending`.
- Phase 4 SQLAlchemy migration is not active; `F4-001`, `F4-002`, and
  `F4-003` remain `pending`.
- Phase 4C offline cached HTML processing and load remains future work.

## Result

Implemented the controlled acquisition runner for approved manifests.

The runner validates the approved manifest, checks `HtmlCache` before every
client request, records cache hits without network calls, fetches cache misses
through an injected `BasketballReferenceClient`-compatible client, stores
fetched HTML through `HtmlCache`, and stops with a partial report on client
failure.

The CLI now exposes `nba-data backfill acquire <manifest.json>` guarded by the
required `--execute-approved-manifest` flag. Unit tests patch the CLI client
with fakes only; no live acquisition was run.

## Next Safe Action

Review `F4B-003` and either close it as `done` after approval or request
changes. Do not start or run `F4B-LIVE-001` without separate explicit owner
approval for the exact manifest.

## Continuation Handoff

- Current branch: `feature/fase-4a-legacy-scraper-consolidation`.
- `F4B-003` implementation is ready for review and should not be marked `done`
  without review approval.
- The next window should first confirm Git status, read the current phase/task
  state, and review the F4B-003 diff.
- If review approves F4B-003, the next safe action is closing `F4B-003` as
  `done`; do not start `F4B-LIVE-001` or run acquisition without separate exact
  manifest approval.

## Guardrails

No live scraping was run. No Basketball Reference contact occurred. No raw HTML
write outside temporary test cache occurred. No DB writes, DB migrations, live
pilot, offline DB loading, legacy/Peewee deletion, API/frontend/OVR, commit,
push, or PR occurred.

## Latest Validation

- `uv run pytest tests/unit/test_backfill_manifest.py`: passed, 15 passed.
- `uv run ruff check src/nba_data/scraping/backfill_manifest.py src/nba_data/cli/main.py tests/unit/test_backfill_manifest.py`:
  passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 70 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  70 passed and 6 Peewee deprecation warnings.
