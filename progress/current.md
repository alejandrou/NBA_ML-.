# Current Work

Status: phase_4b_f4b_001_done

## Active Task

No task is approved, in progress, or needs review.

## Current Phase

- Phase ID: `phase-4b-controlled-raw-html-backfill`
- Phase status: `proposed`
- `F4B-001` is `done`.
- `F4B-002`, `F4B-003`, and `F4B-LIVE-001` remain `pending`.
- Phase 4 SQLAlchemy migration is not active; `F4-001`, `F4-002`, and
  `F4-003` remain `pending`.
- Phase 4C offline cached HTML processing and load remains future work.

## Transition Result

- Confirmed `F4A-001` was `done` in `tasks/feature-list.json` before moving
  the current phase to Phase 4B.
- Confirmed there were no tasks with `approved` or `in_progress` status before
  transition.
- Closed Phase 4A as the legacy scraper consolidation gate.
- Introduced Phase 4B and Phase 4C roadmap/spec documentation.
- Owner explicitly approved implementing `F4B-001` only.
- Promoted `F4B-001` through the workflow and closed it as `done` after
  validation and review.
- Kept Phase 4B as `proposed`; no later Phase 4B task is approved.

## Goal

Phase 4B will define and later implement controlled raw HTML acquisition:

`approved manifest -> BasketballReferenceClient -> HtmlCache -> .html.gz`

The first real pilot defaults to at most five team-season URLs and must be
owner-approved before any live request.

`F4B-001` documented the manifest design, pilot scope, and approval protocol at
`specs/features/F4B-001-controlled-raw-html-backfill-manifest.md`.

## Next Safe Action

Ask the owner whether to approve `F4B-002`, the offline dry-run manifest
validation task. Do not start `F4B-003` or `F4B-LIVE-001` without separate
explicit approval.

## Guardrails

No live scraping was run. No Basketball Reference contact occurred. No DB
writes, DB migrations, controlled backfill execution, offline DB loading,
legacy/Peewee deletion, API/frontend/OVR, commit, push, or PR occurred.

Do not approve or start `F4B-002`, `F4B-003`, or `F4B-LIVE-001` while the phase
is `proposed` without explicit owner approval.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 55 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  55 passed and 6 Peewee deprecation warnings.
