---
id: F6-011
title: Stop validate_database.sh passing without testing, and gate 0007 on a preflight
areas:
  - testing
  - database-schema
  - documentation
priority: 68
depends_on:
  - F5-007
read:
  - scripts/validate_database.sh
  - scripts/validate_postgres_local.py
  - docs/validation/TESTING_STRATEGY.md
  - alembic/versions/0007_team_bref_id_not_null.py
  - README.md
validation:
  - uv run ruff check .
  - uv run pytest -m "not integration and not live"
  - uv run python scripts/validate_postgres_local.py
  - uv run pytest
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Applying migration 0007, or any migration, to the persistent local development database or any shared target. This card builds the preflight that must precede that decision; it never makes the decision and never applies anything.
---

# Goal

`scripts/validate_database.sh` has two defects that point the same way: it
reports success without testing anything, and it applies migrations to a
persistent database with nothing checking whether the data can take them.

Fix both. Repoint the test step at the disposable validator so a green result
means something again, and ship a read-only preflight that answers the one
question standing between migration `0007` and any persistent database.

# Evidence and current state

## The script now passes vacuously

`scripts/validate_database.sh:38` runs:

```bash
uv run pytest tests/integration/test_team_season_loader_postgres.py
```

Since `F5-007`, that test acquires its Session from
`tests/integration/conftest.py`, which refuses to connect unless
`NBA_DATA_TEST_DATABASE=1` **and** the database is named `nba_test_ci` or
prefixed `nba_test_tmp_`. The script sets neither flag, and `:19` defaults
`POSTGRES_DB` to `nba`, which is neither. Observed on 2026-08-21:

```text
$ uv run pytest -ra tests/integration/test_team_season_loader_postgres.py
SKIPPED [1] tests/integration/test_team_season_loader_postgres.py:31:
  NBA_DATA_TEST_DATABASE is not set to exactly '1'. ...
1 skipped, 1 warning in 0.03s
exit code 0
```

pytest exits 0 on a skip, so `:38` succeeds, `:40` prints
`Database validation passed.`, and the script has validated nothing. The skip
itself is correct and is strictly safer than the write it replaced — a test that
seeds the developer's real database was the older, worse behaviour. The defect
is the script reporting that as a pass.

## The script still migrates a persistent database

`scripts/validate_database.sh:36` runs `uv run alembic upgrade head` against the
configured database — `nba`, a persistent local database with a Docker volume
(`docker-compose.yml:11`). `AGENTS.md` lists applying a migration to a
persistent database under *Critical actions — ask first, every time*, and this
script does it unattended, as a side effect of asking for validation.

At head that now means applying `0007_team_bref_id_not_null`, whose `upgrade()`
is a bare `op.alter_column(..., nullable=False)` with **no backfill**. On any
database holding a team row with a null code, it fails partway through a
validation script the developer expected to be safe.

## The blind spot the disposable lane cannot cover

`scripts/validate_postgres_local.py` is green, but it proves the fresh-schema
contract against an empty scratch database. It says nothing about whether an
existing populated database is ready for `0007`.

The `F5-007` review evidence records `0` null-key rows in the configured local
development database on 2026-08-17. That is one measurement of one database at
one time, taken before later work; it is not a standing guarantee, and it covers
no other target. The local development database remains at
`0006_synthetic_team_codes` as of 2026-08-21.

The required check is recorded in prose in `F5-007` and in
`docs/validation/TESTING_STRATEGY.md`, but nothing executes it:

```sql
SELECT count(*) FROM core.teams WHERE basketball_reference_team_id IS NULL;
```

A safety step that exists only as a paragraph is a safety step that gets skipped.

## The documents already disagree

- `README.md:34-41` advertises `bash scripts/validate_database.sh` as "starts
  PostgreSQL, applies migrations, runs the integration test".
- `docs/architecture/IMPACT_MAP.md:164` lists it under **Commands**.
- `docs/validation/TESTING_STRATEGY.md` now tells developers that the script's
  integration step skips and to use `scripts/validate_postgres_local.py`
  instead.

Two documents recommend a script the third says not to rely on.

# Human decisions or resources

- None.

# Acceptance criteria

## `scripts/validate_database.sh`

- It no longer runs `alembic upgrade head` or `alembic check` against the
  configured database. Migration round-tripping already happens inside the
  scratch database that `scripts/validate_postgres_local.py` creates and drops.
- It starts the Docker PostgreSQL service and waits for readiness as it does
  today, then delegates the whole validation to
  `uv run python scripts/validate_postgres_local.py`.
- It propagates that command's exit code. A non-zero result fails the script.
- It cannot print `Database validation passed.` on a run where no integration
  test executed.
- Its header comment states what it now does and that it never writes to the
  configured database.

## The preflight

- A new `scripts/preflight_migration_data.py` reports whether the data
  precondition of `0007_team_bref_id_not_null` holds against an **explicitly
  named** target.
- The target comes from a required `--database-url` argument. It does **not**
  fall back to `Settings.database_url` or `DATABASE_URL`: naming the target is
  the point, and a default would let it silently check the wrong database.
- It executes exactly one statement, the `SELECT count(*)` above, and nothing
  else. No DDL, no writes, no `alembic` invocation, no migration.
- It prints the count and the fully qualified column it counted.
- Exit `0` when the count is `0`; exit non-zero when it is greater, with a
  message saying the migration must not be applied and that remediation is a
  separate decision for the user.
- It never prints the connection password.
- Unit tests cover the zero case, the non-zero case, and the missing-argument
  case, against SQLite or a stubbed connection — the preflight's own tests stay
  offline.

## Documentation

- `README.md`'s database-validation block describes the script's real behaviour
  and names the preflight as the step that precedes any migration of a
  persistent database.
- `docs/architecture/IMPACT_MAP.md`'s **Commands** line for the database
  component lists the preflight alongside the validator, and its **Critical
  actions** line continues to name migration application.
- `docs/validation/TESTING_STRATEGY.md`'s note that the script skips is replaced
  by the corrected description. The section's existing statement of the
  migration blind spot stays, and gains the preflight command.
- All three documents agree on which command to run for which purpose.

# Scope

`scripts/validate_database.sh`, a new `scripts/preflight_migration_data.py`,
a new unit-test module for the preflight under `tests/unit/`, `README.md`,
`docs/architecture/IMPACT_MAP.md` (the database component's **Commands** line
only), and `docs/validation/TESTING_STRATEGY.md`.

# Out of scope

**Applying `0007`, or any migration, to any persistent database.** This card
builds the check that must run first; whether to then migrate is the user's
call, listed under `critical_actions:`.

Backfilling, inventing, or deleting any team row. A non-zero preflight count
stops and reports — it never repairs.

Generalizing the preflight into something that infers data preconditions from
arbitrary pending migrations. `0007` is the only unbackfilled `NOT NULL` in the
history; write the one named check and let a second rule be added when a second
migration needs one.

Changing the safety gate in `tests/integration/conftest.py`, the accepted
database names, or `scripts/validate_postgres_local.py`'s behaviour. The skip
this card responds to is correct; the script reporting it as a pass is not.

The stale migration list at `docs/architecture/IMPACT_MAP.md:163` (it still ends
at `0005`) and the stats table count — both belong to `F4E-023`.

# Impact

`bash scripts/validate_database.sh` changes meaning: it stops touching the
developer's real database and starts running the full disposable lane, so it
becomes slower, genuinely conclusive, and safe to run unattended. Anyone relying
on it to migrate their local database loses that side effect — deliberately,
since that was an unapproved critical action.

The configured local development database stays at `0006_synthetic_team_codes`.
Nothing in this card moves it.

A new `scripts/` entry point and a new unit-test module join the offline suite,
raising its count.

`docs/architecture/IMPACT_MAP.md` is also edited by `F4E-023`; the two touch
different lines, but whichever lands second should re-read the file rather than
assume.

# Implementation notes

The preflight belongs in `scripts/`, not in the `nba-data` CLI. It is an
operator check about a database's readiness for a schema change, not a feature
of the shipped application, and it sits naturally beside
`validate_postgres_local.py` and `validate_tasks.py`.

Require `--database-url` as a positional-or-named argument and let `argparse`
produce the missing-argument error; do not hand-roll it.

Keep the query literal and parameterless. It reads one column of one table, and
the moment it starts composing SQL it becomes something that needs its own
review.

Open the connection read-only where the driver allows it, so the preflight
cannot write even by accident.

`scripts/validate_postgres_local.py` already prints every command it runs and
returns the first failing exit code, so the wrapper needs no output handling of
its own beyond propagating the status.

Do not weaken the conftest gate to make the old script work. That gate is the
reason the vacuous pass is visible at all.

# Durable knowledge updates

- `docs/validation/TESTING_STRATEGY.md` — record the preflight as the required
  step before any migration reaches a persistent database, and correct the
  description of `validate_database.sh`.
- `docs/architecture/IMPACT_MAP.md` — list the preflight under the database
  component's commands.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command:
- Result:

## Manual happy path

1. Run `bash scripts/validate_database.sh` with Docker running and confirm it
   creates and drops a scratch database, runs the whole integration directory
   with tests actually executing, and exits 0.
2. Run the preflight against a disposable database migrated to `0006` that holds
   no team rows.
3. Confirm the configured development database is still at
   `0006_synthetic_team_codes` and unmodified afterwards.

Expected result:

## Manual sad path

1. Run `bash scripts/validate_database.sh` with Docker stopped.
2. Run the preflight with no `--database-url`.
3. Run the preflight against a disposable database seeded with one team row
   whose `basketball_reference_team_id` is null.

Expected result:

## Known limitations

- None.
