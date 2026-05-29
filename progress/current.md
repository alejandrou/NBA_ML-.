# Current Work

Status: phase_4d_acq_001_needs_review

## Active Task

- No active implementation task.
- `F4D-ACQ-001` is `needs_review`.
- `F4D-ACQ-LIVE-001`, `F4D-ACQ-002`, `F4D-001`, `F4D-002`, `F4D-003`, and
  `F4D-004` are `pending`.

## Current Phase

- Phase ID: `phase-4d-full-offline-database-preparation`.
- Phase status: `in_progress`.
- Current subphase: Phase 4D-A controlled NBA team-season cache acquisition.
- Phase 4C offline cached HTML processing and load is closed.
- Phase 4D remains pre-API.

## Latest Checkpoint

- Implemented `F4D-ACQ-001` after explicit owner approval.
- Added deterministic NBA team-season manifest generation for Basketball
  Reference season end years 2000 through 2025.
- The generated manifest contains exactly 775 unique
  `/teams/{TEAM}/{YEAR}.html` URLs.
- Added a dry-run report that checks existing `HtmlCache` paths and reports
  cache hits, missing cache entries, skipped entries, unsupported entries, and
  estimated fetch count.
- Added `uv run nba-data acquisition dry-run-nba-team-seasons`, which prints
  the generated dry-run report as JSON and accepts no manifest path, network
  client, or execution flag.
- Added unit tests for URL shape, franchise lineage boundaries, dry-run cache
  coverage, no-client dry-run signature, module boundary restrictions, and CLI
  JSON output.
- Moved `F4D-ACQ-001` to `needs_review` and set Phase 4D to `in_progress`.
- Left `F4D-ACQ-LIVE-001` and later Phase 4D tasks `pending`.
- Did not fetch HTML, contact Basketball Reference, run live scraping, write
  `.html.gz` files outside temporary tests, write database rows, parse, load,
  backfill, delete data, run destructive migrations, remove Peewee or legacy
  code, implement API/frontend/OVR/ranking/similarity/recommendations/ML work,
  create a branch, commit, push, or open a PR.

## Latest Validation

- `uv run pytest tests/unit/test_nba_team_season_manifest.py`: passed, 7
  passed.
- `uv run ruff check src/nba_data/scraping/nba_team_season_manifest.py src/nba_data/cli/main.py tests/unit/test_nba_team_season_manifest.py`:
  passed.
- `python -m json.tool tasks/feature-list.json`: passed.
- `uv run ruff check .`: passed.
- First `uv run pytest` attempt timed out before returning output; reran with a
  longer timeout.
- `uv run pytest`: passed, 113 passed, 1 skipped, and 6 Peewee deprecation
  warnings.
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`: passed, 113
  passed, 1 skipped, and 6 Peewee deprecation warnings.

## Current Working Tree

- Expected modified files:
  `docs/roadmap/CHANGELOG_LEARNING.md`, `docs/roadmap/CURRENT_PHASE.md`,
  `docs/roadmap/TASKS.md`, `progress/current.md`, `progress/history.md`,
  `specs/phases/phase-4d-full-offline-database-preparation.md`,
  `src/nba_data/cli/main.py`, and `tasks/feature-list.json`.
- Expected untracked files:
  `src/nba_data/scraping/nba_team_season_manifest.py` and
  `tests/unit/test_nba_team_season_manifest.py`.
- These changes include the earlier Phase 4D-A handoff-criteria heading fix
  plus the `F4D-ACQ-001` implementation and progress updates.

## Next Safe Action

- Review `F4D-ACQ-001` against
  `specs/features/F4D-ACQ-001-nba-team-season-manifest.md`.
- If approved, mark `F4D-ACQ-001` as `done` and update review/progress docs.
- If issues are found, move `F4D-ACQ-001` to `changes_requested` and implement
  only the smallest corrective fix.
- Do not start `F4D-ACQ-LIVE-001`, fetch HTML, contact Basketball Reference,
  run live scraping, refresh cache misses, write `.html.gz` files, write
  database rows, parse, load, backfill, delete data, run destructive
  migrations, remove Peewee or legacy code, implement API/frontend/OVR/
  ranking/similarity/recommendations/ML work, create a branch, commit, push, or
  open a PR without separate explicit owner approval.

## Continuation Prompt

Use this prompt to continue in a new Codex window:

```text
Repo: c:\Users\adhc_\Desktop\PYTHON\Projects\Scraping nba-reference
Branch: feature/phase-4c-offline-cached-html-processor

Continue from the F4D-ACQ-001 implementation handoff.

Follow the repo startup protocol first:
1. Read AGENTS.md.
2. Run C:\Program Files\Git\bin\bash.exe scripts/harness/init.sh.
3. Read docs/ai/WORKFLOW_PROTOCOL.md.
4. Read docs/roadmap/PHASE_GOVERNANCE.md.
5. Read docs/roadmap/CURRENT_PHASE.md.
6. Read tasks/feature-list.json.
7. Read specs/phases/phase-4d-full-offline-database-preparation.md.
8. Read specs/features/F4D-ACQ-001-nba-team-season-manifest.md.
9. Read progress/current.md, progress/history.md, and progress/review.md.
10. Run git status --short --branch.

Current state:
- Phase 4D is in_progress.
- F4D-ACQ-001 is needs_review.
- F4D-ACQ-LIVE-001, F4D-ACQ-002, F4D-001, F4D-002, F4D-003, and F4D-004 are pending.
- F4D-ACQ-001 added:
  - src/nba_data/scraping/nba_team_season_manifest.py
  - tests/unit/test_nba_team_season_manifest.py
  - uv run nba-data acquisition dry-run-nba-team-seasons
- The manifest covers Basketball Reference season end years 2000-2025 and contains exactly 775 unique /teams/{TEAM}/{YEAR}.html URLs.
- Dry-run checks HtmlCache paths only and reports cache hits, missing entries, skipped entries, unsupported entries, and estimated fetch count.
- No manifest JSON artifact was committed.
- Expected uncommitted changes include:
  - docs/roadmap/CHANGELOG_LEARNING.md
  - docs/roadmap/CURRENT_PHASE.md
  - docs/roadmap/TASKS.md
  - progress/current.md
  - progress/history.md
  - specs/phases/phase-4d-full-offline-database-preparation.md
  - src/nba_data/cli/main.py
  - tasks/feature-list.json
  - src/nba_data/scraping/nba_team_season_manifest.py
  - tests/unit/test_nba_team_season_manifest.py
- Latest validation passed:
  - uv run pytest tests/unit/test_nba_team_season_manifest.py: 7 passed
  - python -m json.tool tasks/feature-list.json
  - uv run ruff check .
  - uv run pytest: 113 passed, 1 skipped, 6 Peewee deprecation warnings
  - C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh: passed, 113 passed, 1 skipped, 6 Peewee deprecation warnings

Important constraints:
- Do not fetch HTML.
- Do not contact Basketball Reference.
- Do not run live scraping.
- Do not write .html.gz files except temporary test cache files.
- Do not write database rows.
- Do not parse, load, or backfill data.
- Do not implement API, frontend, OVR, ranking, similarity, recommendations, or ML.
- Do not delete raw HTML, database records, Docker/PostgreSQL volumes, Peewee, or legacy code.
- Do not run destructive migrations.
- Do not create a branch, commit, push, or open a PR without explicit owner approval.

Task:
1. Review F4D-ACQ-001 against its feature spec and acceptance criteria.
2. If correct, update progress/review.md, mark F4D-ACQ-001 done, and update progress/current.md, progress/history.md, docs/roadmap/TASKS.md, docs/roadmap/CURRENT_PHASE.md, specs/phases/phase-4d-full-offline-database-preparation.md, docs/roadmap/CHANGELOG_LEARNING.md, and tasks/feature-list.json.
3. If you find an issue, mark F4D-ACQ-001 changes_requested and implement only the smallest corrective fix.
4. Run offline validation after review or fixes.
5. Do not start F4D-ACQ-LIVE-001 without separate explicit owner approval plus the required execution flag.
```
