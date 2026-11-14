---
id: F8-023
title: Close the audit's operational risks R-02 to R-07 and reload the roster
track: shared
areas:
  - scraping
  - database-schema
  - api
  - data-quality
  - documentation
  - testing
priority: 10
depends_on: []
read:
  - docs/validation/DATABASE_AUDIT_2026-11-10.md
  - docs/validation/OFFLINE_DATABASE_PREPARATION.md
  - docs/validation/BACKUP_AND_RESTORE.md
  - src/nba_data/cli/main.py
  - src/nba_data/db/session.py
validation:
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest -m "not integration and not live"
  - uv run pytest -m integration (disposable nba_test_* database)
  - uv run python scripts/validate_tasks.py --all-worktrees
critical_actions:
  - Backing up `nba` and the caches to `D:/nba-backups` before and after the roster reload. Ordered by the owner on 2026-11-14.
  - Reloading the roster into the persistent `nba` (`backfill stats`) from merged `origin/main` (f8057a9), so `birth_date` is parsed (H-06). Ordered by the owner on 2026-11-14.
  - Setting `restart: unless-stopped` on the running `nba_postgres` container (R-04). Ordered by the owner on 2026-11-14.
  - Disabling the legacy `db_manager/` + `scrape_main.py` path (R-05). The owner approved editing those legacy files for this card on 2026-11-14.
---

# Goal

Close what remains of
[the 2026-11-10 database audit](../../docs/validation/DATABASE_AUDIT_2026-11-10.md)
without a schema change: the owner actions H-06 (roster reload) and H-02
(backup after a load), and the risks R-02, R-03, R-04, R-05 and R-07. The
owner merged these into one card on 2026-11-14. The schema group (#12–#16)
stays separate.

# Evidence and current state

- H-06: `stats.player_team_season_roster` has 15,005 rows and 0 `birth_date`
  values on `nba`; the parser fix shipped in f8057a9.
- R-02: every loader selects then inserts; nothing stops two loads at once.
- R-03: `backfill stats`, `player-stats` and `player-postseason-stats` wrap the
  whole archive in one `session.begin()`; a late failure discards ~25 min of work.
- R-04: `nba_postgres` has restart policy `no`.
- R-05: `db_manager/db_conf.py` defaults to the `nba` database and
  `scrape_main.py` scrapes live and creates tables without the approval gate.
- R-07: `/players` and `/teams` sort by name under the server's collation
  (`en_US.utf8`); another collation reorders pages.

# Acceptance criteria

- Every load command takes a PostgreSQL advisory lock before writing and fails
  at once, exit 1, when another load holds it. The load writes through the
  locked connection; if that connection is lost, the load stops instead of
  writing unlocked. Integration-tested, including a terminated backend.
- The three stats producers commit each cached page when run from the CLI; a
  failure keeps the pages already committed. PostgreSQL tests for all three:
  page one survives an interruption on page two, seen from another
  connection, and a rerun completes without duplicates.
- Those commands journal each committed page and the run's outcome to a
  durable `*.progress.jsonl`, since the report is written only at the end.
- `docker-compose.yml` sets `restart: unless-stopped`; the running container has it.
- The legacy entrypoint and Peewee config refuse to run against any database
  unless explicitly pointed at a non-`nba` one; they never default to `nba`.
- Player and team lists order names under a locale-independent collation, with
  the id as tie-breaker. Tested on PostgreSQL. (Chosen: ICU root `und-x-icu`;
  `"C"` byte order was measured and rejected, see Results.)
- Readiness answers 503 when the database lacks that collation.
- `nba` roster has `birth_date` in every row; `validate official-stats` passes
  `missing_required_stat_value` for the roster. Verified backup taken after.
- Docs updated: audit follow-up, load rules, API ordering.

# Results

- Backups verified: `D:/nba-backups/nba-20261114T182339Z-f0c9f944` (before the
  reload) and `nba-20261114T184738Z-9ec22378` (after).
- Roster reload: 805 pages, 0 failed, 134,949 rows; `birth_date` in 15,005 of
  15,005 roster rows. `validate official-stats` with all three producer reports:
  every check 0, including `missing_required_values` and
  `backfill_report_violations`; the only issue is `coverage_artifact_stale` (the
  cache grew after `reports/stats-coverage.json` was built; not caused by this load).
- `nba_postgres` restart policy: `unless-stopped`, applied with `docker update`
  (no restart).
- R-07 measurement on `nba`: `"C"` moved 2,511 of 2,693 players and sent the 8
  names starting with an accented capital after `Z`; ICU root moves 1,738, at
  most 359 places, because glibc `en_US` ignored spaces ("Alan Anderson" before
  "Al Horford"). Teams: 2 positions change.
- Review fixes (2026-11-14): lock bound to the writing connection, progress
  journal, PostgreSQL persistence tests for all three producers, readiness
  collation check. Without the lost-connection guard, its integration test fails.
- Validation: ruff and mypy clean; offline suite 1,961 passed; integration on a
  disposable database 310 passed.

# Review evidence

Second review on 2026-11-14 covered the full working-tree diff against local
`origin/main`, including every new file and the four findings from the first
review. No further blocking implementation findings remain. The owner requested
moving this card to done, committing, and pushing after a successful review.

- `uv run ruff check .`: passed.
- `uv run mypy src/nba_data`: passed, 117 source files.
- `uv run pytest -m "not integration and not live" -q`: 1,961 passed,
  310 deselected; deprecation warnings only.
- `uv run python scripts/validate_postgres_local.py`: 310 passed; migration
  round-trip, refusal guards, and Alembic drift checks passed. The script
  created and removed its own `nba_test_tmp_*` database.
- `uv run python scripts/validate_tasks.py --all-worktrees`: passed before
  closure; repeated after the move to done.
- `git diff --check`: passed.
- Read-only operational checks: roster `count(*) = count(birth_date) = 15005`;
  `nba_postgres` restart policy is `unless-stopped`; both recorded backup
  manifests exist. This review did not repeat the backup content verification
  or reload the persistent database.

Manual checks for a reviewer, using a disposable migrated database and fixture
caches only:

1. Run each stats backfill with its execution flag and a report output path.
   Expect exit 0, a JSON report, and a timestamped progress journal with the
   committed page entries and a completed outcome.
2. Hold the load advisory lock on another connection, then start a backfill.
   Expect immediate exit 1 and no writes. Release it and rerun successfully.
3. Interrupt after page one commits. Expect that page to remain visible from
   another connection and the journal to record the interruption; rerun and
   expect complete results without duplicate natural keys.
4. Terminate the writing backend between pages. Expect the load to stop and
   refuse any write through a replacement backend. The integration test
   exercises this without touching another process's connection.
5. Request player/team lists and readiness. Expect ICU root name order with
   stable id tie-breakers, and readiness 503 if its collation is unavailable.

Known limitations: readers can observe a partial reload; a process crash
between a database commit and its journal append can omit that final journal
entry, and rerunning remains safe. The previously documented stale coverage
artifact is separate from this change. Deployment requires ICU-enabled
PostgreSQL. No live acquisition or persistent database writes ran in this review.

# Cross-track impact

- `/players` and `/teams` page order now follows ICU root collation instead of
  glibc `en_US` (documented in `API_CONTRACT.md`). No field or route changes.
  A deployment needs an ICU-enabled PostgreSQL (the `postgres:16` image is).
  `/health/ready` answers 503 `Database schema not ready` on a server without it.
