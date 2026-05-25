# Current Work

Status: phase_4b_ready_for_roadmap_decision

## Active Task

- `F4B-002` is `done` after review approval and validation.
- `F4B-003` is `done` after owner approval, review approval, and validation.
- `F4B-LIVE-001` is `done` after review approval and offline validation.
- No task is currently `approved`, `in_progress`, or `needs_review`.

## Current Phase

- Phase ID: `phase-4b-controlled-raw-html-backfill`
- Phase status: `proposed`
- `F4B-001`, `F4B-002`, `F4B-003`, and `F4B-LIVE-001` are `done`.
- Phase 4 SQLAlchemy migration is not active; `F4-001`, `F4-002`, and
  `F4-003` remain `pending`.
- Phase 4C offline cached HTML processing and load remains future work.

## Result

Ran the owner-approved `F4B-LIVE-001` pilot.

The exact approved manifest is
`tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`.

Approved URLs:

- `https://www.basketball-reference.com/teams/BOS/2024.html`
- `https://www.basketball-reference.com/teams/DEN/2023.html`

The pilot remains acquisition-only:
`approved manifest -> BasketballReferenceClient -> HtmlCache -> .html.gz`.

Pre-run dry-run result:

- Total entries: 2.
- Cache hits: 1.
- Cache misses: 1.
- Estimated live requests: 1.
- BOS 2024 cache status: hit.
- DEN 2023 cache status: miss.

Acquisition result:

- Total entries: 2.
- Processed entries: 2.
- Cache hits: 1.
- Fetched: 1.
- Failures: 0.
- Live request count: 1.
- BOS 2024 status: cache hit, live requests 0.
- DEN 2023 status: fetched, live requests 1.
- DEN 2023 cache path:
  `data\raw\html\basketball-reference\teams-den-2023.html-4bfff60cb079ffe5.html.gz`.
- DEN 2023 cache file size: 139188 bytes.
- Post-run dry-run result: 2 cache hits, 0 cache misses, 0 estimated live
  requests.

## Next Safe Action

Decide whether to close Phase 4B with a phase transition summary or explicitly
approve a future task. Do not rerun live acquisition, expand the manifest,
start Phase 4C, or start Phase 4 SQLAlchemy migration without separate exact
owner approval.

## Continuation Handoff

- Current branch: `feature/fase-4a-legacy-scraper-consolidation`.
- `F4B-003` is closed as `done`.
- `F4B-LIVE-001` is closed as `done`.
- The owner-approved two-URL manifest pilot is complete and reviewed.
- Do not expand the manifest, create a branch, commit, push, or open a PR
  without separate approval.

## Guardrails

The only live contact in this task was the approved DEN 2023 cache miss through
`nba-data backfill acquire` and `BasketballReferenceClient`. No DB writes, DB
migrations, offline DB loading, parser/load execution, legacy/Peewee deletion,
API/frontend/OVR, commit, push, or PR occurred.

## Latest Validation

- `python -m json.tool tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`:
  passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run nba-data backfill dry-run tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`:
  passed before acquisition with 1 cache hit, 1 cache miss, and 1 estimated
  live request.
- `uv run nba-data backfill acquire tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json --execute-approved-manifest`:
  passed with 1 cache hit, 1 fetched page, 0 failures, and 1 live request.
- `uv run nba-data backfill dry-run tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json`:
  passed after acquisition with 2 cache hits and 0 estimated live requests.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 70 passed and 6 Peewee deprecation warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed,
  70 passed and 6 Peewee deprecation warnings.
- Offline review verified the DEN 2023 gzip cache is readable with 911464
  characters, contains the Denver, `roster`, `totals_stats`, and `advanced`
  markers, and does not contain the wrong-team Boston marker.
