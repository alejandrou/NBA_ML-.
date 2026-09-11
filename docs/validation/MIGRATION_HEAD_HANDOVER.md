# Handover: bringing the persistent `nba` database to the migration head

**Applying a migration to `nba` requires the owner's direct, current instruction
naming the operation and the target. No task card authorizes it.** This document
is the procedure to follow once that instruction exists; it is not the
instruction.

The same four steps — back up, preflight, apply, verify — apply to any future
revision. The worked example is `0008_drop_raw_schema`, the gap
[the 2026-09-08 audit](PROJECT_DATABASE_AUDIT_2026-09-08.md) recorded as its
first finding.

## The gap, closed on 2026-09-12

| | |
|---|---|
| `nba` at | `0008_drop_raw_schema` — the repository head, since [the 2026-09-12 run](#2026-09-12--0008_drop_raw_schema) |
| `nba` was at | `0007_team_bref_id_not_null`, from the F4E-031 run of 2026-09-05 until that upgrade |
| Consequence while behind | `GET /api/v1/health/ready` answered 503 against `nba`, because [the readiness probe](../../src/nba_data/api/services/readiness.py) compares the applied revision set with the repository head |

`0008` drops `raw.scraper_requests`, `raw.scraper_runs`, and `raw.raw_pages`,
then runs `DROP SCHEMA IF EXISTS raw`. The three tables are superseded by the
HTML cache — [ADR 0003](../decisions/0003-cache-raw-html.md) — and the audit
observed all three empty in `nba`.

Two properties of `0008` shape the whole procedure:

- The `DROP SCHEMA` carries **no `CASCADE`**. Any object left in `raw` that the
  revision does not drop by name aborts the upgrade instead of being deleted.
  `scripts/validate_postgres_local.py` proves that refusal on a disposable
  database, and proves the object survives it.
- Its `downgrade()` recreates the three tables' **structure, never their
  contents**. A backup is the only way back to the rows.

## Step 1 — Back up

Take the backup before anything else, and keep it outside the repository working
tree. `nba` was approximately 310 MB at the time of the audit.

```bash
docker compose exec -T postgres pg_dump -U nba -Fc nba > /path/outside/the/repo/nba-before-0008.dump
```

Confirm the file is non-empty and note its size. A snapshot of the
`nba_postgres_data` volume is an acceptable substitute. **Never** run
`docker compose down -v`: that destroys the archive.

## Step 2 — Preflight

`scripts/preflight_migration_data.py` answers, read-only, whether the target is
in the shape the pending revisions require. It opens the database with
`postgresql_readonly=True`, runs count and catalog queries only, and never
applies a revision, repairs a row, or creates an object.

```bash
uv run python scripts/preflight_migration_data.py \
  --database-url postgresql+psycopg://nba:nba@localhost:5432/nba
```

It reports one verdict per migration and exits nonzero if either blocks.

`0007_team_bref_id_not_null` — no `core.teams` row may have a NULL
`basketball_reference_team_id`.

`0008_drop_raw_schema` — the `raw` schema must either be absent, or hold exactly
`raw_pages`, `scraper_runs`, and `scraper_requests`, all empty. The relation
inventory is read from `pg_class` rather than assumed, so an object nobody
expected is found rather than discovered mid-upgrade. Indexes, constraint
indexes, owned sequences, and TOAST tables are excluded, because PostgreSQL drops
those with their parent table.

Expected output on `nba` before the upgrade:

```text
0007_team_bref_id_not_null: core.teams.basketball_reference_team_id NULL count: 0
Preflight passed for 0007_team_bref_id_not_null: the data precondition holds.
0008_drop_raw_schema: schema raw holds 3 relation(s) and 0 routine(s): raw_pages, scraper_requests, scraper_runs
0008_drop_raw_schema: raw.raw_pages row count: 0
0008_drop_raw_schema: raw.scraper_runs row count: 0
0008_drop_raw_schema: raw.scraper_requests row count: 0
Preflight passed for 0008_drop_raw_schema: the data precondition holds.
```

Each blocker means something different, and the command keeps them apart:

| Blocker | What it means | What to do |
|---|---|---|
| `raw.<table> has N row(s)` | The upgrade would discard real rows | Stop. Deciding what those rows are worth is a separate decision, not part of this procedure |
| `raw contains an unrecognized <kind> 'raw.<name>'` | The `DROP SCHEMA` would abort | Stop. Identify the object first; the upgrade cannot succeed while it exists |
| `raw.<table> is missing` | The revision drops it by name and would abort | Stop. The schema is in a state no revision produced |
| `N row(s) have NULL core.teams...` | `0007`'s own precondition is broken | Stop. Unrelated to `0008` |

**Do not proceed past a nonzero exit code.** Remediation is a separate decision.

## Step 3 — Apply

Only with the owner's instruction, and only after steps 1 and 2:

```bash
uv run alembic upgrade head
```

## Step 4 — Verify

```bash
uv run alembic current
```

Expect `0008_drop_raw_schema (head)`.

```bash
uv run python scripts/preflight_migration_data.py \
  --database-url postgresql+psycopg://nba:nba@localhost:5432/nba
```

Expect `schema raw is absent; the revision has nothing left to drop.` and a pass
for both migrations. The absent schema is the post-upgrade shape, not a failure.

Then confirm readiness answers, which is the user-visible point of the whole
exercise:

```bash
uv run nba-data serve
curl -i http://127.0.0.1:8000/api/v1/health/ready
```

Expect `200` with `{"status":"ready"}`, where the same request answered
`503 Database schema not ready` before the upgrade.

## Record the run

Add a dated subsection below when the procedure is actually run: the revision
applied, where the backup went, the preflight output, `alembic current` after,
and the readiness status code. Then update the audit's table counts — `nba` has
44 tables until `0008` lands and 41 afterwards — and
[`IMPACT_MAP.md`](../architecture/IMPACT_MAP.md) if the recorded head changes.

### Applied runs

#### 2026-09-12 — `0008_drop_raw_schema`

Run against the persistent `nba` database under the owner's direct instruction,
following the four steps above in order.

| Step | Observed |
|---|---|
| Target before | `0007_team_bref_id_not_null`; 310 MB; `core` 7 tables, `stats` 33, `raw` 3 |
| Backup | `pg_dump -U nba -Fc` written inside the container, then copied to `Projects/nba-backups/nba-before-0008.dump` outside the repository — 20,948,597 bytes, 2.5 s |
| Backup verified | The host copy was read back into the container: md5 `3a8ad0c45478a56c0bf4e00bbcfade41` on both sides, and `pg_restore -l` listed 409 entries including the `raw` schema, all three tables, and their `TABLE DATA` entries |
| Preflight | Exit 0, matching the expected output above verbatim — `schema raw holds 3 relation(s) and 0 routine(s)`, all three at row count 0 |
| Readiness before | `503 {"detail": "Database schema not ready"}`, logged as `Database is at Alembic revision(s) ['0007_team_bref_id_not_null'], not the migration head(s) ['0008_drop_raw_schema']` |
| `uv run alembic upgrade head` | `0007_team_bref_id_not_null -> 0008_drop_raw_schema`, exit 0, 0.8 s |
| `uv run alembic current` | `0008_drop_raw_schema (head)` |
| Preflight after | Exit 0; `schema raw is absent; the revision has nothing left to drop.` |
| Readiness after | `200 {"status": "ready"}` |
| Target after | `core` 7 tables, `stats` 33, no `raw` schema; 41 application tables, the count the audit predicted |

The container-side dump copies under `/tmp` were removed afterwards. The backup
outside the repository is the only archive of the pre-`0008` `raw` rows — all
three tables were empty, so it preserves nothing the upgrade discarded, but it is
also the route back for everything else in the database.

Readiness was read through an in-process `TestClient` against the configured
target rather than a started server; it is the same application and the same
probe, and it reports the same status code.

### Rehearsed on a disposable database — 2026-09-11 (F6-015)

The four steps above were run end to end against a scratch database on the same
server, created and dropped for the rehearsal. `nba` was not touched, and was
still at `0007_team_bref_id_not_null` when the rehearsal finished; it was
upgraded the next day, under the owner's instruction, in the run recorded above.

| Step | Observed |
|---|---|
| Readiness at `0007` | `503 {"detail": "Database schema not ready"}`, logged as `Database is at Alembic revision(s) ['0007_team_bref_id_not_null'], not the migration head(s) ['0008_drop_raw_schema']` |
| Preflight at `0007` | Exit 0; `schema raw holds 3 relation(s) and 0 routine(s)`, all three tables at row count 0 — the output quoted above, verbatim |
| Preflight with a seeded row, an extra table, and a view in `raw` | Exit 1; three separate blockers — the unrecognized view, the unrecognized table, and `raw.raw_pages has 1 row(s)` |
| `alembic upgrade head` | `0007_team_bref_id_not_null -> 0008_drop_raw_schema` |
| Preflight after the upgrade | Exit 0; `schema raw is absent; the revision has nothing left to drop.` |
| Readiness at head | `200 {"status": "ready"}` |

The audit inferred the 503 from the code without starting a server; this
rehearsal observed it, and observed the 200 that replaces it.

Note what the relation inventory did **not** report at `0007`: three relations,
not the three tables plus the primary-key and unique indexes, the
`ix_raw_scraper_requests_url` index, and the owned sequences that sit in the same
schema. That is the `pg_depend` filter working against a real catalog — without
it, every one of those would be shown to an owner as an unrecognized object.
