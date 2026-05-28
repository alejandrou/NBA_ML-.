# Current Work

Status: phase_4d_acq_001_ready

## Active Task

- No active task.
- `F4D-ACQ-001` is `ready`.
- `F4D-ACQ-LIVE-001`, `F4D-ACQ-002`, `F4D-001`, `F4D-002`, `F4D-003`, and
  `F4D-004` are `pending`.

## Current Phase

- Phase ID: `phase-4d-full-offline-database-preparation`.
- Phase status: `approved`.
- Current subphase: Phase 4D-A controlled NBA team-season cache acquisition.
- Phase 4C offline cached HTML processing and load is closed.
- `F4C-001`, `F4C-002`, and `F4C-003` are reviewed and marked `done`.
- Phase 4D remains pre-API.

## Latest Checkpoint

- Inserted Phase 4D-A as a controlled acquisition subphase inside Phase 4D.
- Added Phase 4D-A task specs for:
  - `F4D-ACQ-001`: Generate NBA team-season URL manifest and dry-run plan.
  - `F4D-ACQ-LIVE-001`: Run owner-approved controlled NBA team-season cache
    acquisition.
  - `F4D-ACQ-002`: Review acquisition report and cache coverage handoff.
- Moved `F4D-ACQ-001` to `ready`.
- Kept `F4D-ACQ-LIVE-001`, `F4D-ACQ-002`, and the existing Phase 4D database
  preparation tasks `pending`.
- Moved existing `F4D-001` back to `pending` and made it depend on
  `F4D-ACQ-002`.
- Documented that seasons 2000-2025 mean Basketball Reference season end years.
- Documented the exact 775-URL NBA team-season manifest expectation.
- Documented acquisition policy: default 10 requests/minute, configurable phase
  max 12 requests/minute, hard cap 20 requests/minute, immediate stop on HTTP
  429, and async only with bounded concurrency plus a global rate limiter.
- Did not fetch HTML, write `.html.gz` files, write database rows, parse, load,
  backfill, implement API/frontend/OVR/ranking/similarity/recommendations/ML
  work, create a branch, commit, push, or open a PR.

## Latest Validation

- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- `uv run pytest`: passed, 106 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 106
  passed, 1 skipped, and 6 Peewee deprecation warnings.

## Next Safe Action

- After validation, request owner approval before implementing `F4D-ACQ-001`.
- `F4D-ACQ-001` must only generate and dry-run the approved NBA team-season URL
  manifest and must not fetch HTML or contact Basketball Reference.
- Do not start `F4D-ACQ-LIVE-001`, run live scraping, contact Basketball
  Reference, refresh cache misses, write `.html.gz` files, write database rows,
  parse, load, backfill, delete data, run destructive migrations, remove Peewee
  or legacy code, implement API/frontend/OVR/ranking/similarity/
  recommendations/ML, create a branch, commit, push, or open a PR without
  explicit owner approval.

## Continuation Prompt

Use this prompt to continue in a new Codex window:

```text
Repo: c:\Users\adhc_\Desktop\PYTHON\Projects\Scraping nba-reference
Branch: feature/phase-4c-offline-cached-html-processor

Continue from the staged Phase 4D-A planning/docs update.

Follow the repo startup protocol first:
1. Read AGENTS.md.
2. Run C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh.
3. Read docs/ai/WORKFLOW_PROTOCOL.md.
4. Read docs/roadmap/PHASE_GOVERNANCE.md.
5. Read docs/roadmap/CURRENT_PHASE.md.
6. Read tasks/feature-list.json.
7. Read specs/phases/phase-4d-full-offline-database-preparation.md.
8. Read specs/features/F4D-ACQ-001-nba-team-season-manifest.md.
9. Read specs/features/F4D-ACQ-LIVE-001-controlled-nba-team-season-cache-acquisition.md.
10. Read specs/features/F4D-ACQ-002-acquisition-report-and-cache-coverage-review.md.
11. Read progress/current.md, progress/history.md, and progress/review.md.
12. Run git status --short --branch.

Current state:
- Phase 4C is closed.
- Current phase is phase-4d-full-offline-database-preparation with status approved.
- Phase 4D-A is the controlled NBA team-season cache acquisition subphase.
- F4D-ACQ-001 is ready.
- F4D-ACQ-LIVE-001, F4D-ACQ-002, F4D-001, F4D-002, F4D-003, and F4D-004 are pending.
- F4D-001 depends on F4D-ACQ-002.
- The staged docs/task update added Phase 4D-A specs and roadmap/progress changes.
- Latest validation passed:
  - python -m json.tool tasks/feature-list.json
  - uv run ruff check .
  - uv run pytest: 106 passed, 1 skipped, 6 Peewee deprecation warnings
  - C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh: passed, 106 passed, 1 skipped, 6 Peewee deprecation warnings

Important constraints:
- Do not fetch HTML.
- Do not contact Basketball Reference.
- Do not run live scraping.
- Do not write .html.gz files.
- Do not write database rows.
- Do not parse, load, or backfill data.
- Do not implement API, frontend, OVR, ranking, similarity, recommendations, or ML.
- Do not delete raw HTML, database records, Docker/PostgreSQL volumes, Peewee, or legacy code.
- Do not run destructive migrations.
- Do not create a branch, commit, push, or open a PR without explicit owner approval.

Task:
1. Verify the staged Phase 4D-A planning/docs diff.
2. Report whether it matches the approved plan.
3. If I explicitly approve implementation in that session, start F4D-ACQ-001 only.
4. F4D-ACQ-001 must generate and dry-run the NBA team-season URL manifest only:
   - seasons 2000-2025 are Basketball Reference season end years;
   - manifest must contain exactly 775 unique NBA team-season URLs;
   - only /teams/{TEAM}/{YEAR}.html URLs are allowed;
   - no network, no HtmlCache writes, no DB writes, no parser/load/backfill.
5. Do not start F4D-ACQ-LIVE-001 without separate explicit owner approval plus the required execution flag.
```
