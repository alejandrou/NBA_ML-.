---
id: F4E-033
title: Drop the redundant core.teams lookup index
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
