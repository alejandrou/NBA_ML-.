---
id: F8-022
title: Bring nba to head and verify off-disk backup recovery
track: data
areas:
  - database-schema
  - documentation
  - testing
priority: 10
depends_on: []
read:
  - docs/validation/DATABASE_AUDIT_2026-11-10.md
  - docs/validation/MIGRATION_HEAD_HANDOVER.md
  - scripts/preflight_migration_data.py
  - src/nba_data/config/settings.py
  - .env.example
validation:
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest -m "not integration and not live"
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Applying 0010–0012 to the persistent `nba` database, from merged `origin/main`. Authorized by the owner's direct instruction of 2026-11-11 (H-01).
  - Taking a fresh `pg_dump -Fc` of `nba` and copying `data/raw/` to a second physical disk. Authorized by the owner on 2026-11-11 (H-02).
  - Editing `DATABASE_URL` in the untracked `.env` (localhost → 127.0.0.1). Authorized by the owner on 2026-11-11 (H-03).
  - Dropping the leftover database `nba_f8006_tmp`. Authorized by the owner on 2026-11-11 (H-14).
  - Owner's follow-up on 2026-11-11 explicitly orders all six review improvements, their documentation, moving this task to done, committing and pushing. This includes a fresh off-disk backup and recovery rehearsals on uniquely named disposable databases; it does not authorize another migration of persistent nba.
---

# Goal

Close the four owner actions of
[the 2026-11-10 database audit](../../docs/validation/DATABASE_AUDIT_2026-11-10.md):
H-01, H-02, H-03, H-14. Unblocks the predictions of #72–#74, which need the `ml`
schema in `nba`.

# Evidence and current state

- H-01: `nba` is at `0009_games_and_box_scores`; the head is
  `0012_ml_predictions`. Readiness answers 503 and the `ml` schema does not
  exist. The audit checked the preconditions of 0010, 0011 and 0012 against
  `nba`, and all three hold.
- H-02: the newest dump, `../nba-backups/nba-before-0009.dump` (2026-10-24), is
  older than the 14,435-game load. `data/raw/` (1.2 GB) lives only on disk C:,
  together with the database and the backups.
- H-03: on Windows `localhost` tries `::1` first and waits for
  `connect_timeout = 5` before falling back to IPv4. The result is about 5 s per
  cold connect against about 30 ms for `127.0.0.1`. The container publishes only
  on `127.0.0.1`. The defaults in `src/nba_data/config/settings.py` and
  `.env.example` use `localhost`.
- H-14: `nba_f8006_tmp` (354 MB) is an F8-006 rehearsal that was never removed.
  It has had no connections since 2026-10-28.

# Human decisions or resources

- [x] The owner ordered all four actions on 2026-11-11.
- [x] Second disk: `D:` (physical disk 1, separate from `C:` on disk 0).

# Acceptance criteria

- A `pg_dump -Fc` of `nba` taken before the upgrade. The copy outside the
  repository must match the container copy by md5, and `pg_restore -l` must
  list it.
- `data/raw/` and `data/models/` copied to `D:\nba-backups\`, with file count
  and byte total equal to the source. The dump is copied there too.
- Preflight exits 0. `alembic current` reports `0012_ml_predictions (head)`.
  The `ml` schema exists, `core.players.slug` and `ix_core_teams_bref_id` are
  gone, and readiness answers 200.
- `DATABASE_URL` uses `127.0.0.1` in `.env`, `.env.example`, and the
  `settings.py` default. A cold connect is measured below 1 s.
- `nba_f8006_tmp` no longer exists.
- The run is recorded in `MIGRATION_HEAD_HANDOVER.md`.
- Both the existing pre-upgrade dump and a fresh current-head dump restore on
  disposable databases, with representative counts verified and recovery to
  head preserving all existing core/stats table counts.
- Raw, model and report copies match by relative path and per-file SHA-256;
  a repeatable non-overwriting backup command and recovery runbook exist.
- Alembic honors the configured connection timeout. Preflight states its
  coverage, rejects unsupported selections, and checks selected 0010–0012
  preconditions. Referenced audits are included as durable dated evidence.

# Scope

`src/nba_data/config/settings.py` (default URL), `.env.example`, the local
`.env` (never committed), docs that quote the `localhost` URL as the
recommended value, `MIGRATION_HEAD_HANDOVER.md`, and the operations above.
The owner's follow-up adds `scripts/backup_database.py`, explicit preflight
selection/checks, Alembic connection configuration, focused offline tests,
backup/recovery documentation, and the two referenced audit files. This expands
the original card's scope under the owner's current instruction.

# Out of scope

The other audit findings (H-04 to H-13, H-15, R-01 to R-05). Loading season 2027
(F8-020, F8-008). Changing the readiness contract. Scheduling unattended backups
or automatic retention. No new migration revision or persistent upgrade.

# Impact

`nba` moves to `0012`. Its readiness flips from 503 to 200, and `ml` becomes
usable. The default connection host changes for every CLI command and for the
API.

# Cross-track impact

- None.

# Implementation notes

Order: dump → off-disk copy → preflight → upgrade → verify → drop the temp
database → change the host. Upgrade only from code identical to `origin/main`.
This branch must hold no revision change.

# Durable knowledge updates

- `docs/validation/MIGRATION_HEAD_HANDOVER.md`: a new dated run.
- `docs/validation/BACKUP_AND_RESTORE.md`: repeatable commands, recovery steps,
  evidence and limits; README and preparation docs link the procedure.
- Preserve both 2026-11-10 audits, with dated follow-up notes rather than
  rewriting their historical findings.

# Review evidence

All four actions were run on 2026-11-11, under the owner's instruction. The full
record is in
[`MIGRATION_HEAD_HANDOVER.md`](../../docs/validation/MIGRATION_HEAD_HANDOVER.md#the-gap-closed-on-2026-11-11-00100012-f8-022).

| Finding | Result |
|---|---|
| H-02 | `nba-before-0010.dump`, 32,801,355 B, md5 `af0c75e2…364e` on all three copies (container, `C:`, `D:`), 407 entries with the game tables. `D:\nba-backups\data\raw` holds 32,806 files and 1,215,350,451 B, equal to the source. `data/models` was copied too |
| H-01 | Preflight exit 0. `alembic upgrade head` exit 0. `alembic current` reports `0012_ml_predictions (head)`. `ml` has 2 tables, and `slug` and `ix_core_teams_bref_id` are gone. Readiness went from 503 to 200 |
| H-14 | `DROP DATABASE nba_f8006_tmp`. The server now holds only `postgres` and `nba` |
| H-03 | `.env`, `.env.example` (`DATABASE_URL`, `POSTGRES_HOST`), and the `settings.py` default now use `127.0.0.1`. Cold connect takes 7–11 ms, and readiness 121 ms (it took 5,222 ms before) |

## Initial automated validation

| Command | Result |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run mypy src/nba_data` | Success: no issues found in 114 source files |
| `uv run pytest -m "not integration and not live"` | 1878 passed, 296 deselected |
| `uv run python scripts/validate_tasks.py --all-worktrees` | Passed |

## Manual happy path

1. `uv run alembic current`
2. `uv run nba-data serve`, then `curl -i http://127.0.0.1:8000/api/v1/health/ready`
3. `Get-ChildItem D:\nba-backups`

Expected result: step 1 prints `0012_ml_predictions (head)`. Step 2 answers
`200 {"status":"ready"}` with no 5 s pause on the first request. Step 3 lists
the four dumps and `data\`.

## Manual sad path

1. `docker compose exec -T postgres psql -U nba -d postgres -c "select datname from pg_database"`
2. `docker compose exec -T postgres psql -U nba -d nba -c "select slug from core.players limit 1"`

Expected result: step 1 does not list `nba_f8006_tmp`. Step 2 fails with
`column "slug" does not exist`.

## Known limitations

- The migration was applied from this branch while its code under `alembic/`
  and `src/` was still identical to `origin/main` (`b094613`). The branch
  changes no revision.
- Backups are event-driven manual runs, not scheduled. The database dump and
  asset directories are not one atomic snapshot; stop writers before backing up.
  A local second disk does not protect against loss of the entire machine.
- Preflight checks only explicitly selected supported revisions (0007/0008 by
  default). It does not discover pending revisions or certify arbitrary schema
  drift. Unsupported pending revisions require manual inspection/rehearsal.
- The CI workflow and tests that use `localhost` as an arbitrary URL were left
  alone. CI runs on Linux, where the delay does not occur.
- `GAME_DATASET_ACQUISITION.md` still names `nba_f8006_tmp`. It is a historical
  record and was not changed.
- One interrupted backup performance trial remains as an unverified partial
  directory, identified in the recovery runbook; it is not a recovery source.

## Follow-up implementation and recovery evidence

The owner explicitly expanded scope and ordered closure after implementation
on 2026-11-11. The six review findings are addressed:

1. Restored `D:/nba-backups/nba-before-0010.dump` (recorded MD5 verified) into
   `nba_test_f8022_88b5e15a7bba`. Selected 0010–0012 preflight checks passed;
   upgrade from 0009 to 0012 preserved all 43 existing core/stats table counts.
   Readiness returned `ready`; scratch database dropped.
2. Added the repeatable `backup_database.py create`/`verify` command and the
   backup-after-acquisition/load/model-write procedure. Created
   `D:/nba-backups/nba-20261111T200805Z-1cde3c08/`: 33,120 assets,
   3,101,161,270 B, and a 32,809,173 B dump. Manifest SHA-256 for the dump:
   `511b946512c1e23f31989097d8a0f7391267ce5df8b2eb37b7398557dd0501e0`.
   This new dump restored at 0012 into `nba_test_f8022_2e880e8212f5`, with the
   same 43 table counts and readiness `ready`; scratch database dropped.
3. New copies are verified by relative path and SHA-256, including models and
   reports, with source-change detection. Same-size corruption, missing/extra
   files, failed dumps and incomplete copies are covered by offline tests.
   The original flat off-disk copy was also independently rehashed: all 32,806
   raw files and both model files match their source paths and SHA-256.
4. Alembic passes `database_connect_timeout_seconds` through `connect_args_for`;
   offline tests exercise the online environment with PostgreSQL and SQLite URLs.
5. Preflight states exact coverage and rejects unknown selections before
   connecting. Supported 0010–0012 checks and blockers have offline tests and
   were exercised against the restored 0009 database. Stale head/coverage claims
   in the operational docs are corrected.
6. Both original audits are included, with dated follow-up notes and working
   links. They preserve the original findings and distinguish subsequent work.

Final persistent checks: `nba` still at 0012, 14,435 games and 474,309 player
lines; HTTP readiness 200. The only non-template application database is `nba`.
Full recovery evidence and reproduction steps are in `BACKUP_AND_RESTORE.md`.

### Final automated validation

| Command | Result |
|---|---|
| `uv run ruff check .` | All checks passed |
| `uv run mypy src/nba_data` | Success, 114 source files |
| `uv run pytest tests/unit/test_backup_database.py tests/unit/test_alembic_connection.py tests/unit/test_preflight_migration_data.py -q` | 37 passed |
| `uv run pytest -m "not integration and not live"` | 1898 passed, 296 deselected; 7 dependency deprecation warnings |
| `uv run python scripts/validate_tasks.py` | Passed |
| `uv run python scripts/validate_tasks.py --all-worktrees` | Passed |
| `git diff --check` | Passed |

No scraping/network acquisition was used. Recovery rehearsals were explicit
owner-authorized operational checks, separate from the offline test suite.

### Closure

The owner explicitly ordered the review follow-ups, documentation, moving this
card to done, committing and pushing on 2026-11-11. No cross-track handoff targets
this card, and it created no new schema/API contract or parked-card bookkeeping.
PR title and description are prepared locally for the pushed task branch;
creating or merging a PR is a separate Git operation.

### Follow-up manual checks

1. Run `backup_database.py verify --backup` on the dated directory above.
   Expected: exit 0 and the recorded dump hash; no database writes.
2. On a disposable copy of the snapshot, alter a file without changing its
   length and verify it. Expected: exit 1, no verified backup reported.
3. Select an unsupported preflight `--revision`. Expected: usage error before
   any connection. Select 0010–0012 only on a restored 0009 target; all pass.
4. Rehearse restoration according to the runbook. Expected: the recorded
   representative counts, preserved counts through upgrade, readiness `ready`,
   and cleanup confined to the scratch database created for that run.
