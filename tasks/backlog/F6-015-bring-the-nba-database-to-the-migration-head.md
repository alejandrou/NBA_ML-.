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

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command:
- Result:

## Manual happy path

1.
2.
3.

Expected result:

## Manual sad path

1.
2.
3.

Expected result:

## Known limitations

- None.
