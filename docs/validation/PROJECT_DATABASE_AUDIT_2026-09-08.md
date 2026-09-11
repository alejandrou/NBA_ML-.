# Project and database audit

Date: 2026-09-08
Repository: `066e513` on `main`
Scope: simple source review and read-only inspection of the existing local PostgreSQL database.

## Overall result

The project has a clear scraper/parser/normalizer/loader separation, a layered GET-only API, migration history, and offline/unit and PostgreSQL integration CI jobs. The database's application tables match the current ORM structure, and the integrity checks performed found no violations.

The main issues are an unapplied migration, broadly privileged database access and network binding, and a configurable scraper delay that can fall below the repository's six-second minimum. This is a bounded audit, not a certification of every stored statistic or production readiness.

## Read-only boundary and target

- Inspected the already-running `nba_postgres` container, database `nba`, through local `docker exec ... psql`. PostgreSQL reports version `16.13`; database size was approximately **310 MB**.
- This is the database identified by the checked-in Compose/default settings. `.env` and secret values were not inspected, so a separately configured API/database target is outside this report.
- Every audit SQL batch used client options `default_transaction_read_only=on`, `statement_timeout=15000`, and `lock_timeout=2000`, followed by `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY` and `ROLLBACK`. PostgreSQL confirmed `transaction_read_only=on`.
- Used catalog reads and SELECT queries only. No migrations, repairs, loaders, scraping, sequence increments, database creation, or data changes were executed. The read-only setting was scoped to audit connections; it does not establish that normal application connections are read-only.
- No services were started or restarted. No credentials, existing project files, task cards, or Git state were changed. This Markdown report is the only intentional filesystem write. PostgreSQL may still maintain its ordinary internal statistics/logs while servicing reads.

## Findings

### 1. Medium — database revision is behind the repository

**Observed:** `public.alembic_version` contains `0007_team_bref_id_not_null`; the repository head resolves to `0008_drop_raw_schema`. The three `raw` tables remain present and are empty.

**Impact:** The current readiness implementation compares the applied revision with the repository head. Against this target, it should report schema-not-ready/HTTP 503 even though the teams and seasons tables exist. This outcome is inferred from the code and revision query; a running HTTP server was not tested.

**Follow-up:** Plan a separately authorized migration after reviewing its effect. Migration 0008 removes the raw tables/schema. Nothing was applied during this audit.

**Resolved 2026-09-12.** The owner authorized the upgrade and it was applied: `nba` is at `0008_drop_raw_schema (head)`, the `raw` schema is gone, and the readiness probe now answers 200 where this report inferred 503. The run — backup, preflight, apply, verify — is recorded in [`MIGRATION_HEAD_HANDOVER.md`](MIGRATION_HEAD_HANDOVER.md). The observations in this report remain as recorded on 2026-09-08; where they count `raw` objects, see that record for the post-upgrade shape.

Evidence: [migration 0008](../../alembic/versions/0008_drop_raw_schema.py), [readiness service](../../src/nba_data/api/services/readiness.py).

### 2. Medium — local database access is broader than the API requires

**Observed:** Docker publishes port 5432 on `0.0.0.0` and IPv6 `[::]`; PostgreSQL has `listen_addresses=*` and SSL disabled. The only non-system role is `nba`, which is a superuser with role/database creation privileges and write privileges on all 44 tables. The checked-in application default uses this role.

**Impact:** The API's read-only behavior is enforced by its code, not by a dedicated SELECT-only database account. Network exposure also extends beyond a loopback binding. Firewall reachability and the application's actual environment overrides were not tested; this is not a finding that the database is publicly accessible.

**Follow-up:** Consider a loopback-only local port binding and a separate read-only API role/connection configuration. Review transport protection if remote access is required.

Evidence: [Compose configuration](../../docker-compose.yml), [settings](../../src/nba_data/config/settings.py), [request session dependency](../../src/nba_data/api/dependencies.py), live `pg_roles`/`table_privileges` queries.

### 3. Medium — scraper configuration can violate the minimum delay

**Observed:** Settings allow `scraper_min_delay_seconds=0` and 20 requests/minute. The central limiter computes `max(configured_delay, 60 / rpm)`, giving **3 seconds**, below the six-second repository minimum. An in-memory check of the limiter reproduced `[3.0]` as the requested sleep; no request was sent and no actual sleep was necessary.

**Impact:** Default settings are compliant, but accepted overrides can break the acquisition pacing rule. The generic client also defaults to one retry after HTTP 429; the two dedicated acquisition CLI paths explicitly set zero retries. The repository's strict stop-on-429 instruction and these generic-client semantics deserve reconciliation.

**Follow-up:** Enforce the six-second floor centrally and cover configuration boundaries with offline tests. Preserve all owner-approval flags and acquisition interlocks.

Evidence: [settings](../../src/nba_data/config/settings.py), [client](../../src/nba_data/scraping/client.py), [CLI](../../src/nba_data/cli/main.py), [existing limiter tests](../../tests/unit/test_rate_limited_client.py).

### 4. Low — redundant team lookup index

**Observed:** `core.teams` has both the unique index `uq_core_teams_bref_id` and the non-unique index `ix_core_teams_bref_id` on the same single column.

**Impact:** The extra index adds storage and write maintenance without an apparent additional lookup benefit. With 37 team rows, the current cost is small.

**Follow-up:** Evaluate removing it in future schema work. Both indexes were left intact.

Evidence: live `pg_index` definitions and [core models](../../src/nba_data/db/models/core.py).

### 5. Low — some guidance describes implemented features as future work

The [API skill](../../.agents/skills/api-fastapi/SKILL.md) calls readiness a future task, while the implementation and API contract include it. The [API architecture testing section](../architecture/API_ARCHITECTURE.md) describes PostgreSQL integration as future work, while tests and a CI job already exist.

These are documentation conflicts, not reasons to remove working features. Update the descriptions in a separate change.

## Database structure and integrity

| Area | Observed result |
| --- | --- |
| Schemas | `core`, `stats`, `raw`, `public` |
| Tables | 44: 7 core, 33 stats, 3 raw, 1 migration-version table (41 since `0008` dropped the 3 raw tables on 2026-09-12) |
| Columns inspected | 1,229 across those tables |
| ORM comparison | All 40 application tables present; no column name, type, length, numeric precision/scale, or nullability differences |
| Keys | All 121 application primary/unique/foreign-key definitions match by columns and FK targets |
| Entire DB constraint inventory | 44 primary keys, 42 unique constraints, 41 foreign keys, 4 CHECK constraints; none unvalidated |
| Indexes | 90; all valid and ready |
| Sequences | 43 present; all 40 application sequences checked against maximum IDs, none behind |
| Other objects | No user views, materialized views, foreign tables, routines, or non-internal triggers found in the audited schemas |
| Extensions | `plpgsql` only |
| Schema separation | Core identity and official stats are separate; no `features` schema or generated metric tables observed |

The model comparison did not perform a full Alembic autogeneration diff or compare every default expression and CHECK expression text. Foreign keys and indexes were inspected without exercising writes.

### Data checks

- **130 aggregate checks passed:** application foreign-key orphans, blank statistics lineage, negative game counts, supported shooting percentage ranges, and cross-season player/team links.
- The additional raw request-to-run orphan check passed.
- **28 comparisons** confirmed matching identity sets between each stats family and its totals table, beyond merely comparing row counts.
- Regular-season player totals and team-stint totals passed the checked arithmetic rules: points from field goals/free throws, field-goal and rebound components, makes not exceeding attempts, and starts not exceeding games. NULL operands are not treated as failures, so this does not prove completeness.
- All 2,551 players have nonblank source IDs. All 37 teams have nonblank names, and none uses its code as its name.
- All 775 alias ranges have both bounds and are ordered correctly.
- Synthetic team-code CHECK constraints exist on team IDs/abbreviations, aliases, and team-season abbreviations. No unvalidated constraints were found.

### Coverage and schema limitations

The database contains **26 NBA seasons, 2000–2025**, and **775 team-seasons**: 29 per year for 2000–2004 and 30 per year for 2005–2025. This records observed scope; seasons outside it were not assessed as missing.

There are **12,676 player-seasons**, **14,344 team stints**, and a roster stats row for every stint. Regular-season totals cover 12,667 player-seasons and 14,332 stints. All nine player-seasons without regular-season totals have postseason totals. These gaps may reflect postseason-only participation or roster/non-playing records; source-cache reconciliation is needed before calling them defects.

The nine player-season gaps are: `jonesdw02/2013`, `mcgratr01/2013`, `hollajo02/2016`, `wrighdo01/2016`, `lawsoty01/2018`, `adamsja01/2020`, `vildolu01/2022`, `jeffrda01/2023`, and `thomptr01/2023`.

Some rules rely on application validation: player source IDs are nullable in the schema, alias ranges have no ordering CHECK, and player-team-season links do not have a database constraint requiring both parents to reference the same season. No corresponding bad data was found. Nullable historical statistics should not automatically be considered errors.

## Project checks performed

| Check | Result |
| --- | --- |
| Initial Git inspection | Clean working tree on `main` |
| `.venv/Scripts/ruff.exe check . --no-cache` | Passed |
| `.venv/Scripts/python.exe -B scripts/validate_tasks.py` | Passed |
| `git diff --check` | Passed before report creation |
| In-memory Python AST parsing | Passed for 144 Python files under src/tests/alembic/scripts |
| In-memory API/OpenAPI inspection | Six versioned paths: health, readiness, team list/detail, season list/detail |
| Repository migration-head resolution | `0008_drop_raw_schema` |
| Offline limiter calculation | Reproduced the three-second override issue |

Source inspection found dedicated SELECT query repositories, deterministic pagination ordering, one engine per API app, request-scoped sessions, and no scraper imports in the inspected API flow. CI defines separate offline and disposable-PostgreSQL validation jobs; their latest run status was not queried.

The full pytest suite, mypy, integration tests, build/install commands, migration round trips, and live acquisition were **not run**. Some create fixture/cache/database artifacts and are outside this strict read-only audit. No external website was contacted, and no external dependency vulnerability scan was performed.

Backups, restoreability, remote access controls, physical corruption, query performance under load, every statistic's source accuracy, and cache-file existence were not verified. Separate SQL batches have separate snapshots, so concurrent application changes could affect comparisons.

## Exact table inventory

Counts below are exact SELECT counts taken during the audit, not planner estimates.

| Table | Rows |
| --- | ---: |
| `core.player_seasons` | 12,676 |
| `core.player_team_seasons` | 14,344 |
| `core.players` | 2,551 |
| `core.seasons` | 26 |
| `core.team_aliases` | 775 |
| `core.team_seasons` | 775 |
| `core.teams` | 37 |
| `public.alembic_version` | 1 |
| `raw.raw_pages` | 0 |
| `raw.scraper_requests` | 0 |
| `raw.scraper_runs` | 0 |
| `stats.player_postseason_adj_shooting` | 5,301 |
| `stats.player_postseason_advanced` | 5,301 |
| `stats.player_postseason_pbp` | 5,301 |
| `stats.player_postseason_per_game` | 5,301 |
| `stats.player_postseason_per_minute` | 5,301 |
| `stats.player_postseason_per_poss` | 5,301 |
| `stats.player_postseason_shooting` | 5,301 |
| `stats.player_postseason_totals` | 5,301 |
| `stats.player_season_adj_shooting` | 12,667 |
| `stats.player_season_advanced` | 12,667 |
| `stats.player_season_pbp` | 12,667 |
| `stats.player_season_per_game` | 12,667 |
| `stats.player_season_per_minute` | 12,667 |
| `stats.player_season_per_poss` | 12,667 |
| `stats.player_season_shooting` | 12,667 |
| `stats.player_season_totals` | 12,667 |
| `stats.player_team_postseason_adj_shooting` | 5,301 |
| `stats.player_team_postseason_advanced` | 5,301 |
| `stats.player_team_postseason_pbp` | 5,301 |
| `stats.player_team_postseason_per_game` | 5,301 |
| `stats.player_team_postseason_per_minute` | 5,301 |
| `stats.player_team_postseason_per_poss` | 5,301 |
| `stats.player_team_postseason_shooting` | 5,301 |
| `stats.player_team_postseason_totals` | 5,301 |
| `stats.player_team_season_adj_shooting` | 14,332 |
| `stats.player_team_season_advanced` | 14,332 |
| `stats.player_team_season_pbp` | 14,332 |
| `stats.player_team_season_per_game` | 14,332 |
| `stats.player_team_season_per_minute` | 14,332 |
| `stats.player_team_season_per_poss` | 14,332 |
| `stats.player_team_season_roster` | 14,344 |
| `stats.player_team_season_shooting` | 14,332 |
| `stats.player_team_season_totals` | 14,332 |
