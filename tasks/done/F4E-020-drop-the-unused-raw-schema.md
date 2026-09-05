---
id: F4E-020
title: Drop the unused raw schema
areas:
  - database-schema
  - documentation
priority: 40
depends_on: []
read:
  - src/nba_data/db/models/raw.py
  - alembic/versions/0001_initial_raw_core.py
  - alembic/env.py
  - docs/decisions/0003-cache-raw-html.md
  - docs/architecture/IMPACT_MAP.md
validation:
  - uv run pytest tests/unit/test_impact_map_documentation.py tests/unit/test_migration_snapshots.py
  - uv run ruff check .
  - uv run pytest
  - bash scripts/validate_database.sh
critical_actions:
  - Applying revision 0008 to a persistent or shared database requires explicit owner approval; authoring the reversible revision and running it against the disposable local lane does not.
  - Before the owner applies 0008 anywhere persistent, the three tables must be confirmed empty against that database. This card assumes emptiness from code evidence only.
  - Never edit migration 0001_initial_raw_core.py. Revision 0008 supersedes it by dropping what 0001 created.
---

# Goal

Drop `raw.raw_pages`, `raw.scraper_runs`, and `raw.scraper_requests`, their ORM
models, and the `raw` schema, via a new reversible Alembic revision. Record the
disposition in the ADR that made the filesystem cache authoritative, so a future
audit does not re-file the tables as missing data.

The owner's decision on 2026-08-25 was **drop all three**. This card implements
that decision; it no longer decides anything.

# Evidence and current state

## All three tables exist and none is ever written

[`src/nba_data/db/models/raw.py`](../../src/nba_data/db/models/raw.py) declares
`raw.raw_pages`, `raw.scraper_runs`, and `raw.scraper_requests`, all created by
migration `0001`. Grepping the whole repository for `RawPage`, `ScraperRun`,
`ScraperRequest`, and the three table names finds hits **only** in the model
module, `db/models/__init__.py`, `alembic/env.py`, migration `0001`, and
`tests/unit/test_raw_models.py`. There is no writer and no reader anywhere,
including the legacy read-only trees `scrap/`, `models/`, `db_manager/`, and
`utils/`. Three tables, fully modeled, entirely inert.

## Why the run tables cannot be rescued

`raw.scraper_runs` and `raw.scraper_requests` record what happened during a
fetch: run grouping, `run_type`, `config_json`, per-request `http_status`,
`cache_hit`, `requested_at`, and error text. None of that survives in the cache —
the files are the *outcome*, not the transcript. For scrapes already performed
the information is simply gone. A backfill would manufacture plausible values,
which is worse than an empty table because it looks like provenance.

## Why `raw_pages` is dropped even though it is recoverable

`raw_pages` is genuinely reconstructible. A verification script run against the
live archive on 2026-08-25 reconstructed a URL for **all 3,326** cached files —
775 team-season pages and 2,551 player pages — and confirmed every one by
recomputing `sha256(url)[:16]` and matching it against the filename. Zero
unmatched.

It is dropped anyway because **nothing would read it, and the cache index it
would provide already exists twice in code**:

- [`cache_inventory.py:219-232`](../../src/nba_data/scraping/cache_inventory.py#L219-L232)
  already derives `source_url`, `cache_path`, team, and season for each cached
  team-season file;
  [`player_page_cache.py`](../../src/nba_data/scraping/player_page_cache.py)
  does the player-page equivalent.
- The F4E-017 stats-coverage artifact already carries `cache_path` plus a
  SHA-256 content fingerprint of the decompressed bytes
  ([`stats_coverage.py:963-978`](../../src/nba_data/validation/stats_coverage.py#L963-L978)).

`raw_pages` would be a third representation of the same facts with no consumer.
The filesystem cache plus the JSON reports in `reports/` remain the source of
truth for v1, exactly as ADR 0003 says.

Note for whoever revisits this: neither existing discovery path verifies the
digest — both template-match the filename and stop. The digest verification
described above was written for this card and is not in the codebase.

## What the drop breaks, and must be fixed with it

[`tests/unit/test_raw_models.py:9-11`](../../tests/unit/test_raw_models.py#L9-L11)
asserts `fetched_at.server_default is not None` on all three timestamp columns.
That file is deleted with the models.

[`alembic/env.py`](../../alembic/env.py) has `include_name` returning
`name in {"raw", "core", "stats"}` for schemas. `raw` must come out, or
`alembic check` keeps reflecting a schema no model targets.

`IMPACT_MAP.md` line 174 says `` `raw` (3 tables) ``; line 173 lists
`db/models/{raw,core,stats}.py`; line 180 lists `test_raw_models.py`; line 178's
migration chain is **already stale**, stopping at `0005` when the head is
`0007_team_bref_id_not_null`. All four need correcting.

## Migration facts the implementer needs

- The chain head is the revision **id** `0007_team_bref_id_not_null`. Revision
  ids in this repo do **not** always match filenames — `0005`'s `down_revision`
  is `0004_player_season_src_team` and `0007`'s is `0006_synthetic_team_codes`.
  Read the `revision:` string out of the file rather than assuming.
- `0001`'s `upgrade` does `CREATE SCHEMA IF NOT EXISTS raw`, creates the three
  tables, and creates `ix_raw_scraper_requests_url`. Its `downgrade` is the
  exact drop order to copy.
- The disposable validation lane migrates to `0007`, snapshots the full `raw`
  catalog, upgrades and downgrades `0008`, and compares the restored columns,
  types, nullability, defaults, constraints, and indexes with that snapshot. It
  also injects an unexpected `raw` table and requires the no-`CASCADE` upgrade
  to fail without deleting it. `alembic check` alone cannot prove either fact
  because `alembic/env.py` deliberately excludes the retired `raw` schema.

# Human decisions or resources

- [x] **1. Does `raw.raw_pages` get populated at all in v1?** No — it is
      **dropped**. It is recoverable, but nothing reads it and the cache index
      already exists in `cache_inventory.py`, `player_page_cache.py`, and the
      stats-coverage artifact. (Owner, 2026-08-25.)
- [x] **2. Rule for `http_status` and `fetched_at` on reconstructed rows.**
      Moot under the drop, recorded so it is not re-litigated: if `raw_pages` is
      ever reinstated, reconstructed rows pass **explicit NULL** for both, and
      `server_default=func.now()` **stays** so a genuine live fetch still stamps
      itself. Omitting the column is never acceptable — it silently records the
      time of the backfill. (Owner, 2026-08-25.)
- [x] **3. Do `scraper_runs` / `scraper_requests` stay?** No — both are
      **dropped**, and neither is ever backfilled for past scrapes. Run
      provenance starts whenever it is deliberately reinstated. (Owner,
      2026-08-25.)
- [x] **4. Where is the disposition recorded?** In
      `docs/decisions/0003-cache-raw-html.md` and
      `docs/architecture/IMPACT_MAP.md`. Not a code comment — the code is being
      deleted.
- [x] **5. Migration and `pg_dump`?** A new revision `0008`, yes. The tables are
      empty by construction — no code path has ever written them — so a dump is
      not required by this card. Confirming emptiness against any persistent
      database, and deciding whether to dump it first, belongs to the owner at
      apply time and is listed under `critical_actions`.

# Acceptance criteria

- A new Alembic revision `0008_drop_raw_schema` exists with
  `down_revision = "0007_team_bref_id_not_null"`. Its `upgrade` drops
  `ix_raw_scraper_requests_url`, then `raw.scraper_requests`, then
  `raw.scraper_runs`, then `raw.raw_pages`, then executes
  `DROP SCHEMA IF EXISTS raw`.
- That revision's `downgrade` recreates the `raw` schema and all three tables
  with the same columns, nullability, server defaults, unique constraint
  `uq_raw_pages_url_content_hash`, foreign key to `raw.scraper_runs.id`, and
  index `ix_raw_scraper_requests_url` that `0001` created. Proven inside
  `bash scripts/validate_database.sh` by comparing a PostgreSQL catalog snapshot
  at `0007` with the snapshot after the `0008` downgrade; the command must pass
  clean.
- `alembic/versions/0001_initial_raw_core.py` is byte-identical to its current
  content: `git diff` over that path is empty.
- `src/nba_data/db/models/raw.py` is deleted; `RawPage`, `ScraperRun`, and
  `ScraperRequest` are gone from `db/models/__init__.py` (import and `__all__`)
  and from both tuples in `alembic/env.py`.
- `include_name` in `alembic/env.py` no longer returns `True` for the `raw`
  schema.
- `tests/unit/test_raw_models.py` is deleted, and no test anywhere imports the
  three models.
- `grep -rn "RawPage\|ScraperRun\|ScraperRequest\|raw_pages\|scraper_runs\|scraper_requests" src/ tests/ alembic/ docs/`
  returns hits only inside `alembic/versions/0001_initial_raw_core.py` and the
  new `0008` revision.
- `docs/decisions/0003-cache-raw-html.md` states the outcome: the filesystem
  cache plus the JSON reports in `reports/` are the source of truth, the `raw`
  schema was dropped unpopulated by revision `0008`, and its "store metadata in
  PostgreSQL later" consequence is explicitly superseded. It names what would
  have to be true for a metadata table to return, so this reads as a decision
  rather than an omission.
- `docs/architecture/IMPACT_MAP.md`'s Database section no longer lists a `raw`
  schema, `db/models/raw.py`, or `test_raw_models.py`, and its migration chain
  line runs through `0008`. The stale `0006`/`0007` gap on that line is fixed in
  passing.
- `docs/specs/PROJECT_SPEC.md:13` no longer lists `raw` as a live initial schema.
- `F4E-028`'s decision 2 no longer offers "`raw.raw_pages` rows written at fetch
  time" as an option, since that table will not exist; that card records instead
  that reinstating it would require a new revision. **Already satisfied** when
  `F4E-028` was prepared on 2026-08-27 — confirm the wording in
  `tasks/backlog/F4E-028-record-fetch-provenance-in-the-html-cache.md` still
  holds and change nothing if it does.
- `uv run python scripts/validate_tasks.py` passes.

# Scope

`alembic/versions/0008_drop_raw_schema.py` (new), `alembic/env.py`,
`src/nba_data/db/models/raw.py` (deleted),
`src/nba_data/db/models/__init__.py`, `tests/unit/test_raw_models.py` (deleted),
`docs/decisions/0003-cache-raw-html.md`, `docs/architecture/IMPACT_MAP.md`,
`docs/architecture/SYSTEM_DESIGN.md`, `docs/specs/PROJECT_SPEC.md`,
`.agents/skills/db-schema/SKILL.md`, and `scripts/validate_postgres_local.py`.
The option-4 line in `F4E-028` is already gone; that card now lives at
`tasks/backlog/F4E-028-record-fetch-provenance-in-the-html-cache.md` and needs
no edit from this one.

# Out of scope

Migration `0001`, which is never edited. The filesystem cache layout, which
`IMPACT_MAP.md` protects. `HtmlCache.path_for_url`'s output shape, which
`cache_inventory.py` and both backfill discovery paths depend on. Live scraping.
Applying any migration to a persistent database. The `core` and `stats` schemas.
Whether the cache should record fetch provenance going forward — that is
`F4E-028`, which this card unblocks but does not answer.

# Impact

- **Schema:** the `raw` schema and its three tables cease to exist once `0008`
  is applied. Nothing reads them, so no runtime behaviour changes.
- **Migrations:** the chain head moves from `0007_team_bref_id_not_null` to
  `0008_drop_raw_schema`. Anyone on an older database picks the drop up on the
  next `alembic upgrade head`.
- **Tests:** `test_raw_models.py` disappears.
  `test_impact_map_documentation.py` parses only the `stats` count, so the
  `raw` line changing does not affect it; it is in `validation:` because it is
  the test that notices IMPACT_MAP drift at all.
- **`F4E-028`:** its decision 2 loses one option and its decision 4 is settled —
  nothing backfills provenance for pages already cached, because there is no
  longer a table to backfill into.
- **A future rebuild-and-diff card:** simplified, since there is no `raw` schema
  to reproduce or diff.

# Implementation notes

Write the `0008` downgrade by copying the three `op.create_table` calls out of
`0001`'s `upgrade` verbatim, including `server_default=sa.func.now()` on
`fetched_at`, `started_at`, and `requested_at`, and the `postgresql.JSONB()`
type on `config_json`. A downgrade that quietly changes a default or a
nullability is a silent schema fork; the disposable lane's before-and-after
PostgreSQL catalog comparison proves it did not happen. The Alembic drift check
does not inspect `raw` after this revision because the schema is excluded from
`include_name`.

Order matters in `upgrade`: drop the index, then `scraper_requests` (it holds
the foreign key), then `scraper_runs`, then `raw_pages`, then the schema.

Use `DROP SCHEMA IF EXISTS raw` without `CASCADE` — if anything unexpected still
lives in that schema, the migration should fail loudly rather than delete it.

Preserve the separation invariant at `SYSTEM_DESIGN.md:99` and
`IMPACT_MAP.md:183` and `:199`, but name the retired layer "cached raw source
material" rather than implying that `raw` tables or a `raw` schema still exist.

# Durable knowledge updates

- `docs/decisions/0003-cache-raw-html.md` — record the raw-schema disposition
  and supersede "store metadata in PostgreSQL later".
- `docs/architecture/IMPACT_MAP.md` — the cache stands alone; the database does
  not index it. Fix the stale migration chain line while there.
- `docs/specs/PROJECT_SPEC.md` — `raw` is no longer a live schema.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command: `uv run pytest tests/unit/test_impact_map_documentation.py tests/unit/test_migration_snapshots.py`
- Result: Passed, 11 tests.
- Command: `uv run ruff check .`
- Result: Passed with no findings.
- Command: `uv run pytest`
- Result: Passed, 871 tests; 25 environment-dependent integration tests skipped.
- Command: `& 'C:\Program Files\Git\bin\bash.exe' scripts/validate_database.sh`
- Result: Passed. The exact wrapper migrated a disposable database to `0007`,
  proved the `0008` downgrade restored an identical `raw` catalog, proved an
  unexpected `raw` table makes the upgrade fail without deleting that table,
  upgraded to `0008`, passed Alembic's drift check, and passed all 26 PostgreSQL
  integration tests. The disposable database was dropped.
- Command: `uv run python scripts/validate_tasks.py`
- Result: Passed after activation; run again after the move to review.

## Manual happy path

1. Start the repository's disposable PostgreSQL service with
   `docker compose up -d postgres`.
2. Run `uv run python scripts/validate_postgres_local.py`.
3. Confirm the output includes the `0008_drop_raw_schema` upgrade, the
   downgrade to `0007_team_bref_id_not_null`, the re-upgrade, and two clean
   Alembic drift checks.

Expected result: The disposable migration round trip and PostgreSQL integration
suite pass, and the temporary database is removed.

## Manual sad path

1. Run `bash scripts/validate_database.sh`; it migrates an isolated disposable
   database to `0007` and creates `raw._unexpected_0008_guard`.
2. The validator attempts to upgrade to `0008_drop_raw_schema` and requires a
   nonzero exit.
3. It confirms the unexpected table remains, removes it, completes the clean
   upgrade, and drops the disposable database.

Expected result: The final `DROP SCHEMA IF EXISTS raw` fails because it does not
use `CASCADE`, and transactional DDL preserves the unrecognized object. This
path passed in the recorded automated validation.

## Known limitations

- No persistent database was inspected or migrated. Before applying `0008` to
  one, the owner must confirm all three legacy tables are empty and decide
  whether a backup is warranted.
