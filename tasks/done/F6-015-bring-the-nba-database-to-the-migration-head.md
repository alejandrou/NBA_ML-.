---
id: F6-015
title: Bring the nba database to the migration head behind a preflight check
areas:
  - database-schema
  - api
  - testing
  - documentation
priority: 44
depends_on: []
read:
  - alembic/versions/0008_drop_raw_schema.py
  - scripts/preflight_migration_data.py
  - scripts/validate_postgres_local.py
  - src/nba_data/api/services/readiness.py
  - tests/unit/test_preflight_migration_data.py
  - tests/integration/test_preflight_migration_data_postgres.py
  - docs/validation/OFFLINE_DATABASE_PREPARATION.md
  - docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md
  - tasks/done/F6-011-repoint-database-validation-and-add-migration-preflight.md
validation:
  - uv run pytest tests/unit/test_preflight_migration_data.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - bash scripts/validate_database.sh
critical_actions:
  - Running `alembic upgrade head` against the persistent `nba` database is a critical action. It needs the owner's direct, current instruction naming the operation and the target. This card does not authorize it; it only makes the step safe to authorize.
  - The preflight opens its target read-only and runs count queries. It must never repair a row, create an object, or apply a revision.
  - Take a backup or snapshot of `nba` before the owner applies 0008. The upgrade drops three tables and a schema; the downgrade recreates their structure, never their contents.
---

# Goal

Close the gap between the persistent `nba` database and the repository migration
head, and make the step verifiable before anyone runs it. `nba` sits at
`0007_team_bref_id_not_null`; the head is `0008_drop_raw_schema`. Until it is
applied, `GET /api/v1/health/ready` reports schema-not-ready against this
database.

Finding 1 of [the 2026-09-08 project and database audit](../../docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md).

# Evidence and current state

- `public.alembic_version` in `nba` contains exactly one row,
  `0007_team_bref_id_not_null`. The repository head resolves to
  `0008_drop_raw_schema` (`alembic/versions/0008_drop_raw_schema.py:14`), and
  `docs/architecture/IMPACT_MAP.md:176` records the same chain.
- `src/nba_data/api/services/readiness.py:69-77` compares the applied revision
  set with `migration_heads()` and returns `ReadinessOutcome.SCHEMA_NOT_READY`
  when they differ, which the router answers as HTTP 503. Against `nba` today
  that is the expected outcome even though `core.teams` and `core.seasons` exist
  and are populated. The audit inferred this from the revision query and the
  code; it did not start a server.
- The three `raw` tables are present and **empty**: `raw.raw_pages` 0 rows,
  `raw.scraper_runs` 0 rows, `raw.scraper_requests` 0 rows. Nothing in
  `src/nba_data/` writes them — ADR 0003
  (`docs/decisions/0003-cache-raw-html.md:17`) records that the HTML cache
  superseded them.
- `alembic/versions/0008_drop_raw_schema.py:20-25` drops the three tables and
  then runs `DROP SCHEMA IF EXISTS raw` **without** `CASCADE`. Any unrecognized
  object left in `raw` therefore aborts the upgrade instead of being deleted.
  `scripts/validate_postgres_local.py:100-109` already proves both halves of that
  behavior on a disposable database — an exact downgrade round trip, and a
  refusal that leaves the unexpected object intact.
- `scripts/preflight_migration_data.py` exists from F6-011 but checks exactly one
  precondition, `0007`'s: `core.teams.basketball_reference_team_id IS NULL`
  (`preflight_migration_data.py:21-27`). There is no check for `0008`, so no
  read-only command tells an owner whether the raw schema is in the shape 0008
  requires.
- `docs/validation/OFFLINE_DATABASE_PREPARATION.md:466-472` already states that
  closing a migration gap on `nba` is itself a critical action needing its own
  approval, and names `0008` as the revision to expect.

# Human decisions or resources

- [x] Whether 0008 should be applied at all is settled: ADR 0003 records that the
      `raw` tables are superseded, they are empty, and the audit's follow-up asks
      for exactly this. What still requires the owner's direct, current
      instruction is *running* it against `nba`, which `critical_actions` records.

# Acceptance criteria

- `scripts/preflight_migration_data.py` gains a `0008` precondition check against
  the same explicitly named `--database-url` target, reported alongside the
  existing `0007` check:
  - the `raw` schema either is absent, or contains **only** `raw_pages`,
    `scraper_runs`, and `scraper_requests` — any other relation, view, sequence,
    or routine is reported as a blocker, because it would abort the upgrade;
  - every present raw table is empty, and a nonzero count is reported as a
    blocker naming the table and the count, because 0008 discards those rows.
- The command still refuses an empty or non-PostgreSQL URL, still opens the
  target with `READ_ONLY_EXECUTION_OPTIONS`, and still applies no revision. Its
  exit code is nonzero when any precondition blocks.
- Unit coverage extends `tests/unit/test_preflight_migration_data.py`: the
  argument and URL guards keep their behavior, a clean raw schema passes, a
  populated raw table blocks, and an unrecognized raw object blocks.
- Integration coverage extends
  `tests/integration/test_preflight_migration_data_postgres.py`, including a case
  proving the new check runs on a connection that cannot write — the guarantee
  `test_the_preflight_connection_cannot_write_to_the_target` already asserts.
- `bash scripts/validate_database.sh` still passes end to end on a disposable
  database, including the existing 0008 upgrade/downgrade round trip.
- The ordered procedure is recorded in a validation document: back up, run the
  preflight against `nba`, apply, verify.
- **Only after the owner's direct instruction**, and recorded in the review
  evidence: `nba` reports `0008_drop_raw_schema` in `alembic_version`, the `raw`
  schema is gone, and `GET /api/v1/health/ready` answers 200 against it. If that
  instruction does not arrive, the card is still complete — it ships the
  preflight, its tests, and the procedure, and says plainly that the apply step
  was not run.

# Scope

`scripts/preflight_migration_data.py`,
`tests/unit/test_preflight_migration_data.py`,
`tests/integration/test_preflight_migration_data_postgres.py`, and one validation
document.

# Out of scope

Editing any file in `alembic/versions/`, including 0008 — migrations are never
edited, only superseded. Changing the readiness contract, its outcomes, or its
status codes. Changing the 0008 round trip already in
`scripts/validate_postgres_local.py`. Backfills, loaders, or any data change on
`nba`. Any later revision, including the one F4E-021 introduces.

# Impact

Adds a second precondition to the one command an owner runs before an authorized
migration, so that command's output shape changes. Once 0008 is applied, `nba`
loses the `raw` schema and its 44 tables become 41 — the audit's inventory and
any document quoting "44 tables" goes stale. Readiness against `nba` flips from
503 to 200.

# Implementation notes

Follow the shape F6-011 established: one explicit target, no variable
interpolation into the URL, read-only execution options, one count query per
precondition, and a per-check verdict rather than one opaque pass/fail.

Read the raw inventory from `pg_class`/`information_schema` rather than trusting
a hardcoded list of three names to be exhaustive — the whole point of the check
is to find the object nobody expected.

Keep the empty-table blocker and the unknown-object blocker separate, with
separate messages. An owner who reads "raw.raw_pages has 12 rows" makes a
different decision from one who reads "raw contains an unrecognized table".

# Durable knowledge updates

- `docs/validation/OFFLINE_DATABASE_PREPARATION.md` — its handover preflight step
  1 says "close the migration gap"; point it at the new check.
- `docs/architecture/IMPACT_MAP.md` — only if the applied head actually moves.

# Review evidence

## What was and was not done

The preflight, its tests, and the procedure ship. The apply step was **not** part
of the card's implementation: `alembic upgrade head` against `nba` needs the
owner's direct, current instruction, and the card does not supply it. The whole
four-step procedure was rehearsed against a scratch database created and dropped
for the purpose, so the document records observed output rather than predicted
output.

**The owner then gave that instruction, and the upgrade was applied on
2026-09-12.** `nba` is at `0008_drop_raw_schema (head)`, readiness answers 200,
and the run — backup, preflight, apply, verify — is recorded in
[`MIGRATION_HEAD_HANDOVER.md`](../../docs/validation/MIGRATION_HEAD_HANDOVER.md#2026-09-12--0008_drop_raw_schema).
The final acceptance criterion is met, by that separate instruction rather than
by this card.

## Automated validation

| Command | Result |
|---|---|
| `uv run pytest tests/unit/test_preflight_migration_data.py` | 17 passed |
| `uv run ruff check .` | All checks passed |
| `uv run mypy src/nba_data` | Success: no issues found in 70 source files |
| `uv run pytest` | 892 passed, 27 skipped |
| `bash scripts/validate_database.sh` | PostgreSQL validation passed; 28 integration tests passed, including the 4 in `test_preflight_migration_data_postgres.py`. The existing 0008 round trip still holds: "Revision 0008 downgrade exactly restored the raw schema catalog" and "Revision 0008 rejected an unrecognized raw object without deleting it" |
| `uv run python scripts/validate_tasks.py` | Passed |

Docker Desktop was not running; it was started so the database lane could run.

### Rehearsal on a disposable database, 2026-09-11

Scratch database `nba_test_tmp_preflightdoc` on the same server, dropped
afterwards; `select datname from pg_database where datname like 'nba_test_tmp%'`
returned nothing, and `nba` — untouched by the rehearsal — still reported
`0007_team_bref_id_not_null` at that point.

1. Readiness at `0007`: **503** `{"detail": "Database schema not ready"}` — the
   audit inferred this from the code; it is now observed.
2. Preflight at `0007`: exit **0**, `schema raw holds 3 relation(s) and 0
   routine(s): raw_pages, scraper_requests, scraper_runs`, all three row counts 0.
   Three relations, not the tables plus their indexes and owned sequences.
3. Preflight with one row inserted into `raw.raw_pages`, one extra table, and one
   view added to `raw`: exit **1**, three separate blockers.
4. `alembic upgrade head`, then preflight: exit **0**, `schema raw is absent`.
5. Readiness at head: **200** `{"status": "ready"}`.

## Manual happy path

Read-only against the real `nba`. Nothing here changes it.

1. `docker compose up -d postgres`
2. Run the preflight against `nba`:
   ```bash
   uv run python scripts/preflight_migration_data.py \
     --database-url postgresql+psycopg://nba:nba@localhost:5432/nba
   ```
3. Confirm `nba` is where it was:
   ```bash
   docker compose exec -T postgres psql -U nba -d nba -tAc "select version_num from alembic_version"
   ```

Expected result: step 2 exits 0 and prints a verdict for each migration — the
`0007` NULL count at 0, then `Preflight passed` for both. Step 3 prints the
revision unchanged: the command applied nothing.

The `0008` verdict depends on when you run this. Since the 2026-09-12 upgrade the
honest answer is `schema raw is absent; the revision has nothing left to drop.`
and step 3 prints `0008_drop_raw_schema`. Before it, the same command printed
`schema raw holds 3 relation(s) and 0 routine(s): raw_pages, scraper_requests,
scraper_runs` with all three row counts 0, and step 3 printed
`0007_team_bref_id_not_null`. Both are passes; only the shape of the schema
differs.

## Manual sad path

Part A — the argument guards, which need no database at all:

1. `uv run python scripts/preflight_migration_data.py --database-url ""`
2. `uv run python scripts/preflight_migration_data.py --database-url sqlite:///./local.db`

Expected result: both exit 2 before any connection is opened, naming the problem
(`cannot be empty`, `not 'sqlite'`). No password is echoed back.

Part B — the blockers. **Use a disposable database, never `nba`:**

1. `docker compose exec -T postgres psql -U nba -d nba -c 'CREATE DATABASE nba_test_tmp_sadpath'`
2. `DATABASE_URL=postgresql+psycopg://nba:nba@localhost:5432/nba_test_tmp_sadpath uv run alembic upgrade 0007_team_bref_id_not_null`
3. Seed the two different kinds of problem:
   ```bash
   docker compose exec -T postgres psql -U nba -d nba_test_tmp_sadpath \
     -c "insert into raw.raw_pages (url, source, cache_path, content_hash, status) values ('u','s','p','h','ok')" \
     -c "create table raw._unexpected_guard (id integer)"
   ```
4. Run the preflight against `nba_test_tmp_sadpath`.
5. `docker compose exec -T postgres psql -U nba -d nba -c 'DROP DATABASE nba_test_tmp_sadpath'`

Expected result: step 4 exits 1 and reports the two problems *separately* —
`raw contains an unrecognized table 'raw._unexpected_guard'; DROP SCHEMA raw runs
without CASCADE and would abort the upgrade.` and `raw.raw_pages has 1 row(s);
0008_drop_raw_schema discards them.` — followed by `Migration 0008_drop_raw_schema
must not be applied.` and `Remediation is a separate decision for the user.`
Nothing is repaired, and the seeded objects are still there at step 5.

## Known limitations

- **The apply step is not done.** `nba` remains at `0007` and
  `GET /api/v1/health/ready` still answers 503 against it. Everything needed to
  authorize it is in place; the instruction is yours to give.
- The integration lane runs at head, where `raw` is already gone, so it can only
  exercise the schema-absent branch on a real server. The populated-table and
  unknown-object branches are covered by unit tests against a stub, and were
  additionally exercised against real PostgreSQL in the rehearsal above. Wiring a
  `0007`-stage preflight call into `scripts/validate_postgres_local.py` would
  close that gap permanently, but changing that script is out of this card's
  scope.
- The `0008` check enumerates relations (`pg_class`) and routines (`pg_proc`) in
  `raw`. A standalone enum type or domain in that schema would not be listed; it
  would still abort the upgrade safely, which
  `scripts/validate_postgres_local.py` already proves leaves the object intact.
- One file outside the card's stated scope changed: `.agents/index.md` gained a
  row for the new document, which would otherwise be unroutable. The line count
  it records for `OFFLINE_DATABASE_PREPARATION.md` (258) was already stale before
  this card — that file is 642 lines — and was left alone.
- `git mv` staged the card's move out of `tasks/backlog/`. Nothing is committed,
  and unstaging it needs a Git command this card does not authorize.
