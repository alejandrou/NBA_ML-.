# Current Work

Status: phase_2_f2_live_001_needs_review

## Active Task

No task is approved or in progress.

## Current Phase

- Phase ID: `phase-2-scraper-cache-integration`
- Phase status: `in_progress`
- Awaiting review: `F2-LIVE-001` - Run one-page live smoke test for adapted
  team-season scraper.
- Last completed task: `F2-004` - Adapt legacy team-season scraper entrypoint
  to use client/cache.

## Goal

Review the controlled one-page live smoke test result for the approved URL and
either close `F2-LIVE-001` as `done` or request changes.

## Smoke Test Result

- URL: `https://www.basketball-reference.com/teams/BOS/2024.html`
- Cache result: miss before execution.
- Cache path:
  `data\raw\html\basketball-reference\teams-bos-2024.html-8ef926a311c6bcbf.html.gz`
- Cache exists after: `True`.
- Live requests: 1.
- HTTP status: 200.
- HTML chars: 928025.
- Parsed tables: `['advanced', 'roster', 'totals']`.
- Legacy roster rows: 19.
- Legacy totals rows: 19.
- Legacy advanced rows: 19.

## Latest Validation

- `uv run ruff check .`: passed.
- `uv run pytest`: 29 passed, 3 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  29 passed, 3 Peewee deprecation warnings.

## Notes

The live request went through `BasketballReferenceClient`. `OneRequestHttpClient`
was only injected as the underlying HTTP transport fuse and printed
`http_status=200`.

No database writes were performed, no database migration was applied, no
historical scraping was run, no concurrency was used, no additional URLs were
requested, no Peewee or legacy code was deleted, and no API/frontend/OVR work
was implemented.
