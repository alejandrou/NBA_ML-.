---
id: F4E-033
title: Drop the redundant core.teams lookup index
track: data
areas:
  - database-schema
  - testing
priority: 30
depends_on: []
read:
  - src/nba_data/db/models/core.py
  - alembic/versions/0001_initial_raw_core.py
  - alembic/versions/0008_drop_raw_schema.py
  - scripts/validate_postgres_local.py
  - tests/integration/test_team_schema_contract_postgres.py
  - docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md
validation:
  - uv run pytest tests/unit/test_core_models.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - bash scripts/validate_database.sh
critical_actions:
  - Applying the new revision to the persistent `nba` database requires the owner's explicit, current approval. Authoring the reversible revision and running it against the disposable local lane does not.
  - Never edit `alembic/versions/0001_initial_raw_core.py`. The new revision supersedes it by dropping the index 0001 created.
---

# Goal

Remove one of the two indexes `core.teams` carries on
`basketball_reference_team_id`. The unique constraint already provides a backing
index on that exact column; the second, non-unique index adds storage and write
maintenance and serves no lookup the first cannot.

Finding 4 of [the 2026-09-08 project and database audit](../../docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md).

# Evidence and current state

- `src/nba_data/db/models/core.py:29-38` declares both on the same single column:
  `UniqueConstraint("basketball_reference_team_id", name="uq_core_teams_bref_id")`
  and `Index("ix_core_teams_bref_id", "basketball_reference_team_id")`.
- `alembic/versions/0001_initial_raw_core.py:86` creates
  `ix_core_teams_bref_id`, and line 121 drops it on downgrade. That is the only
  migration that touches it.
- PostgreSQL implements a unique constraint with a unique B-tree index, so
  `uq_core_teams_bref_id` already answers every equality and prefix lookup
  `ix_core_teams_bref_id` could answer. The audit confirmed both indexes exist,
  are valid, and are ready.
- The cost today is small: `core.teams` holds 37 rows. This is tidiness in the
  schema definition, not a performance fix — say so rather than claiming a win
  the row count cannot support.
- Nothing names the index outside the model and migration 0001. A repository-wide
  search for `ix_core_teams_bref_id` returns only those two files and the audit.

# Human decisions or resources

- [x] Which of the two to drop: the non-unique `ix_core_teams_bref_id`. The
      unique index cannot be dropped — it enforces the constraint that makes the
      Basketball Reference team ID the natural key F5-007 keyed the API on.

# Acceptance criteria

- A new reversible Alembic revision drops `ix_core_teams_bref_id` from
  `core.teams` on upgrade and recreates it on downgrade, with the same name and
  the same column.
- `Index("ix_core_teams_bref_id", ...)` is removed from `Team.__table_args__` in
  `src/nba_data/db/models/core.py`. The unique constraint, both synthetic-code
  check constraints, and the `{"schema": "core"}` entry are untouched.
- `uv run alembic check` reports no difference between the models and the
  migration chain after the revision is applied to a disposable database — the
  model and the schema must not disagree in either direction.
- `bash scripts/validate_database.sh` passes: it round-trips the whole chain,
  including the new revision, on a uniquely named disposable database, and its
  existing 0008 upgrade/downgrade assertions still hold.
- The team API and its query repository behave identically. Lookups by
  Basketball Reference team ID still resolve, still return the same rows, and
  still use an index — confirm with `EXPLAIN` on the disposable database and
  record the plan, rather than assuming.
- The revision is **not** applied to the persistent `nba` database as part of
  this card.

# Scope

One new file under `alembic/versions/`, and the `Team.__table_args__` block in
`src/nba_data/db/models/core.py`.

# Out of scope

Every other index in the schema — the audit counted 90 and found the other 89
unobjectionable. Any other table's `__table_args__`. The unique constraint
itself. The two synthetic team-code check constraints. Adding new indexes, or
tuning any query. Applying the revision to `nba`.

# Impact

`core.teams` loses one index, so writes to that table do one less index update
and the database drops the corresponding storage. `docs/architecture/IMPACT_MAP.md`
records the migration chain and gains a link. The audit's "Indexes: 90" figure
becomes 89 once applied.

# Implementation notes

Chain the revision onto whatever `alembic heads` reports at implementation time,
not onto a number assumed now. F4E-021 also introduces a revision (`0009`) and
F6-015 may move the applied head, so whichever lands second sets its
`down_revision` to the other. Never renumber or edit an existing revision to make
room.

Follow the existing revision file style: module docstring naming the revision and
what it does, the four module-level `revision`/`down_revision`/`branch_labels`/
`depends_on` variables, and an `op.drop_index(...)`/`op.create_index(...)` pair
that name the schema explicitly, exactly as `0001_initial_raw_core.py:86` and
`:121` do.

If `uv run alembic check` reports a difference the revision did not intend, that
is a signal the model edit and the migration disagree — fix the pair, do not
silence the check.

# Durable knowledge updates

- `docs/architecture/IMPACT_MAP.md:176` — extend the migration chain with the new
  revision.

# Cross-track impact

- None.

# Review evidence

## Automated validation

- Command: `uv run pytest tests/unit/test_core_models.py`
- Result: 9 passed. Includes the new
  `test_team_bref_id_is_indexed_only_by_its_unique_constraint`.
- Command: `uv run ruff check .`
- Result: All checks passed.
- Command: `uv run mypy src/nba_data`
- Result: Success: no issues found in 99 source files.
- Command: `uv run pytest`
- Result: 1592 passed, 257 skipped (the integration lane, which needs a database).
- Command: `bash scripts/validate_database.sh` (run twice, exit 0 both times)
- Result: whole chain upgraded on a disposable `nba_test_tmp_*` database; the
  existing 0008 assertions held ("Revision 0008 downgrade exactly restored the raw
  schema catalog", unrecognized raw object rejected); `0010` upgraded, downgraded
  and re-upgraded, with "The head revision's downgrade exactly restored
  0009_games_and_box_scores" (a catalog comparison of `core` and `stats`);
  `alembic check`: "No new upgrade operations detected."; integration lane 258
  passed; temporary database dropped.
- Command: the query plans, run on two fresh disposable databases (37 rows,
  the size of `core.teams` in `nba`, and 5,001 rows). The procedure, so anyone
  can reproduce it with `psql` against a disposable `nba_test_tmp_*` database:

  ```bash
  DATABASE_URL=<disposable-url> uv run alembic upgrade 0009_games_and_box_scores
  ```

  ```sql
  INSERT INTO core.teams (basketball_reference_team_id, current_abbreviation, current_name)
  SELECT 'T' || g, 'T' || g, 'Team ' || g FROM generate_series(1, 37) g;  -- or 5001
  ANALYZE core.teams;
  SELECT indexname FROM pg_indexes WHERE schemaname = 'core' AND tablename = 'teams' ORDER BY 1;
  EXPLAIN SELECT * FROM core.teams WHERE basketball_reference_team_id = 'T7';
  BEGIN; SET LOCAL enable_seqscan = off;
  EXPLAIN SELECT * FROM core.teams WHERE basketball_reference_team_id = 'T7';
  COMMIT;
  ```

  Then `DATABASE_URL=<disposable-url> uv run alembic upgrade 0010_drop_redundant_team_index`,
  run `ANALYZE` and the queries above again, and drop the database.
- Result: the indexes went from `ix_core_teams_bref_id, teams_pkey, uq_core_teams_bref_id`
  at `0009` to `teams_pkey, uq_core_teams_bref_id` at `0010`. The plans were
  identical at both revisions, and the lookup returned the same row `(7, 'T7')`:

  | Rows | `enable_seqscan` | Plan at `0009` and at `0010` |
  |---|---|---|
  | 37 | on | `Seq Scan on teams (cost=0.00..1.46 rows=1)` |
  | 37 | off | `Index Scan using uq_core_teams_bref_id (cost=0.14..8.16 rows=1)` |
  | 5,001 | on | `Index Scan using uq_core_teams_bref_id (cost=0.28..8.30 rows=1)` |
  | 5,001 | off | `Index Scan using uq_core_teams_bref_id (cost=0.28..8.30 rows=1)` |

  On a 37-row table PostgreSQL picks a sequential scan whichever indexes exist,
  which is the right call at that size. What matters is that the unique index
  stays available, and that the planner was already picking it over
  `ix_core_teams_bref_id` before the drop. So the index this card removes was
  not serving any plan for this lookup.

## Manual happy path

1. `uv run alembic heads` → `0010_drop_redundant_team_index (head)`, a single head.
2. `bash scripts/validate_database.sh` → ends "PostgreSQL validation passed",
   with the `0010` round-trip line and "No new upgrade operations detected."
3. On a disposable database at head, `\d core.teams` lists `teams_pkey` and
   `uq_core_teams_bref_id` only, and `EXPLAIN` of a lookup by
   `basketball_reference_team_id` shows an Index Scan on `uq_core_teams_bref_id`.

Expected result: one head, clean validation, one fewer index, same plan.

## Manual sad path

1. On a disposable database at head, `uv run alembic downgrade 0009_games_and_box_scores`.
2. `\d core.teams` → `ix_core_teams_bref_id` is back, on `basketball_reference_team_id`.
3. Restore `Index("ix_core_teams_bref_id", ...)` in `Team.__table_args__` without
   the revision, upgrade to head, run `uv run alembic check`.

Expected result: step 2 shows the index recreated with the same name and column;
step 3 fails `alembic check` (and the new unit test), showing model and chain
must agree.

## Known limitations

- Not applied to the persistent `nba` database; that needs the owner's approval
  after merge, following the release steps below. `0010` has no data
  precondition, so `scripts/preflight_migration_data.py` gained no check for it.
- From this revision's merge until it is applied, `GET /api/v1/health/ready`
  answers 503 against `nba` (`nba` at `0009`, head `0010`), as it did for `0009`.
  The API's team queries themselves still work and still have an index.
- The benefit is tidiness only: `core.teams` holds 37 rows in `nba`.
- `docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md` is a dated audit and
  still reads "Indexes: 90"; it was left as the record of that date.
- Outside the stated scope: `tests/unit/test_core_models.py` (one regression
  test, which checks by columns that no standalone index covers
  `basketball_reference_team_id` and that only `uq_core_teams_bref_id` does; it
  fails if a duplicate index is added under another name, which I checked by
  adding one temporarily) and the preflight sentence on `IMPACT_MAP.md:192`.

## Release steps (owner, after merge)

Each step needs the owner's explicit, current instruction. This card authorizes
none of them. The procedure is `docs/validation/MIGRATION_HEAD_HANDOVER.md`.

1. From merged `origin/main`, take a backup of `nba` and verify it.
2. `uv run python scripts/preflight_migration_data.py --database-url <nba-url>`
   → every verdict passes.
3. `uv run alembic upgrade head` against `nba`, then `uv run alembic current`
   → `0010_drop_redundant_team_index (head)`.
4. On `nba`, the `pg_indexes` query above → `teams_pkey`, `uq_core_teams_bref_id`.
5. `GET /api/v1/health/ready` → 200 (it answers 503 between merge and step 3).
   A team lookup by Basketball Reference ID returns the same team as before.
6. Record the run in `MIGRATION_HEAD_HANDOVER.md`.
