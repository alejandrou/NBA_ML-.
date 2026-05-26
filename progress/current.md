# Current Work

Status: phase_4_sqlalchemy_ready_for_owner_approval

## Active Task

- No task is currently `approved`, `in_progress`, or `needs_review`.
- `F4-001` is `ready`, not approved.
- `F4-002` and `F4-003` remain `pending`.

## Current Phase

- Phase ID: `phase-4-sqlalchemy-migration`
- Phase status: `proposed`
- Phase 4B controlled raw HTML backfill is closed.
- Phase 4C offline cached HTML processing and load remains future work.

## Transition Summary

Closed Phase 4B after the reviewed completion of `F4B-001`, `F4B-002`,
`F4B-003`, and `F4B-LIVE-001`.

Phase 4B produced and verified the controlled acquisition path:

`approved manifest -> BasketballReferenceClient -> HtmlCache -> .html.gz`

The owner-approved pilot used only:

- `https://www.basketball-reference.com/teams/BOS/2024.html`
- `https://www.basketball-reference.com/teams/DEN/2023.html`

No additional live acquisition, Basketball Reference contact, parser/load
execution, DB write, migration, raw HTML deletion, legacy/Peewee deletion,
API/frontend/OVR work, branch creation, commit, push, or PR occurred during the
phase transition.

## Next Safe Action

Ask the owner before promoting `F4-001` from `ready` to `approved`. The next
approved implementation should keep the migration scope reviewable and preserve
Peewee coexistence.

## Continuation Handoff

- Current branch: `feature/fase-4-sqlalchemy-migration`.
- `phase-4-sqlalchemy-migration` is current with status `proposed`.
- `F4-001` is the next candidate task and is `ready`, not approved.
- Do not implement `F4-001`, run migrations, delete data, create a branch,
  commit, push, or open a PR without separate approval.

## Guardrails

- No live scraping or Basketball Reference contact without exact owner approval.
- No destructive migrations or data deletion.
- No Peewee or legacy scraper deletion.
- No Phase 4C offline load, API/frontend, generated metrics, OVR, ranking,
  similarity, or ML work.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 70 passed and 6 Peewee deprecation warnings.
- `uv run alembic check`: failed with existing nullable drift on
  `raw.raw_pages.fetched_at`, `raw.scraper_requests.requested_at`, and
  `raw.scraper_runs.started_at`.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh`: passed.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  70 passed and 6 Peewee deprecation warnings.
