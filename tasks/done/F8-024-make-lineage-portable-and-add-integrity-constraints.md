---
id: F8-024
title: Make lineage portable and add integrity constraints
track: data
areas:
  - database-schema
  - scraping
  - data-quality
  - testing
priority: 85
depends_on: []
read:
  - docs/validation/DATABASE_AUDIT_2026-11-10.md
  - docs/validation/MIGRATION_HEAD_HANDOVER.md
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
  - src/nba_data/db/models/stats.py
  - src/nba_data/db/models/core.py
  - src/nba_data/scraping/cache.py
  - src/nba_data/scraping/offline_processor.py
  - src/nba_data/scraping/loaders/games.py
  - src/nba_data/db/repositories/stats.py
  - src/nba_data/validation/official_stats.py
  - src/nba_data/api/services/readiness.py
  - scripts/preflight_migration_data.py
  - scripts/validate_postgres_local.py
validation:
  - uv run pytest tests/unit/test_cache_key.py tests/unit/test_preflight_migration_0013.py tests/unit/test_game_models.py tests/unit/test_game_loader.py tests/unit/test_stats_repositories.py tests/unit/test_offline_stats_backfill.py tests/unit/test_offline_player_stats_backfill.py tests/unit/test_offline_player_postseason_stats_backfill.py tests/unit/test_official_stats_validation.py tests/unit/test_preflight_migration_data.py
  - uv run pytest tests/integration/test_lineage_migration_postgres.py tests/integration/test_preflight_migration_data_postgres.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - bash scripts/validate_database.sh
  - uv run python scripts/validate_tasks.py --all-worktrees
critical_actions:
  - Applying the new revision (0013) to the persistent nba database — from merged origin/main, after a verified backup, with writers paused, with the owner's direct instruction. The revision rewrites cache_path in place in every lineage table (about 830,000 rows: ~329,000 in the season tables plus ~503,000 in the two game tables).
---

# Goal

One Alembic revision that closes audit items #12 and #15
(`docs/validation/DATABASE_AUDIT_2026-11-10.md`):

- **H-07:** `cache_path` stores a machine-independent key relative to the cache
  root instead of an absolute Windows path, for existing rows and every future
  load.
- **H-12 (in part):** the four `totals` tables get a few cheap `CHECK`
  constraints. The `NOT NULL` on the public player key moved to the `shared`
  card F8-025 during implementation (see Implementation notes).
- **H-09** (box-score lineage repeated on every player line) only if the owner
  chooses it below.

This closes the audit's schema items for the current scope. It does not promise
that later feature or ML work will need no further schema change.

# Evidence and current state

- **Two lineage formats in one column (H-07).** 100 % of
  `stats.player_season_totals` (13,249) and `stats.player_team_season_totals`
  (14,993) rows hold `C:\Users\<user>\...\data\raw\html\basketball-reference\<file>.html.gz`;
  all 474,309 `stats.player_game_totals` rows hold
  `data\raw\html\basketball-reference\<file>.html.gz`.
- **Where the value comes from.** Producers store `str(path)` of the path they
  actually read: `offline_games_backfill.py:189-191`,
  `loaders/current_season_games.py:398-400`,
  `offline_player_stats_backfill.py:216,232,239,269`,
  `offline_player_postseason_stats_backfill.py:226,245,252,299`,
  `loaders/player_page_stats.py:142-151`, `loaders/team_season_stats.py:741-742`,
  `offline_loader.py:146-147` via `offline_processor.py:184`. Its format depends
  on whether `SCRAPER_CACHE_DIR` was absolute at load time.
- **Two ways a file is chosen.** `HtmlCache.path_for_url`
  (`scraping/cache.py:125-142`) derives the canonical
  `<root>/<host_dir>/<slug>-<digest16>.html.gz` from a URL. But
  `offline_processor._resolve_explicit_cache_path` (`offline_processor.py:277-291`)
  accepts any `.html.gz` under the root, absolute or relative, with any name;
  its tests use `basketball-reference/fixture.html.gz` and a file directly under
  the root (`tests/unit/test_offline_processor.py:62,176,213`). So the stored key
  must be **the real file read, relativised**, not the canonical key of the URL.
  Absolute *inputs* stay legal; only absolute *stored lineage* is rejected.
- **Nothing reads `cache_path` back from the database to open a file.** It is
  written, compared (`loaders/games.py:645-647`), excluded from the API
  (`db/repositories/queries/player_stats.py:105-117`) and checked by
  `validation/official_stats.py:40,823`. `validation/stats_coverage.py` uses its
  own inventory and already has `_relative_posix_path`. `src/nba_data/ml/` does
  not use it.
- **Missing integrity (H-12).** `core.players.basketball_reference_player_id`
  is nullable (`db/models/core.py:99`), 0 NULLs in `nba`; the API filters
  `is_not(None)` (`queries/players.py:33,49`). The 32 wide tables and the roster
  have no `CHECK`; the 4 totals tables use `_TotalsColumnsMixin`
  (`db/models/stats.py:102-131`). Audit §5: 0 negatives, 0 percentages outside
  [0, 1], 0 arithmetic inconsistencies. Pattern to copy: game-table checks frozen
  in `0009` and pinned by `tests/unit/test_game_models.py`.
- **`efg_pct` bound disagrees with the validator.** eFG% ≤ 1.5 (all makes are
  threes), but `official_stats.py:68,1484` groups `efg_pct` with `ts_pct` and
  allows both up to 2. A row the validator passes could be rejected by the new
  database `CHECK`.
- **Readiness is head-sensitive.** `api/services/readiness.py:84-89` answers 503
  when the applied revision differs from the package head. Shipping `0013` to
  `main` while `nba` stays at `0012` makes the API not-ready until it is
  applied; old loaders writing absolute paths would also be rejected by the new
  format `CHECK`.
- **Preflight is a closed registry.** `scripts/preflight_migration_data.py:295-301`
  maps revisions `0007`–`0012` to checks; `0013` has none.
- **The round-trip check runs on empty tables.**
  `scripts/validate_postgres_local.py:181-209` compares catalogs after
  `downgrade -1`; it would not notice a downgrade that loses data.
- **H-09 evidence.** In `player_game_totals`, lineage plus timestamps are 85 of
  135 MB (audit); 14,435 distinct `cache_path` for 474,309 rows. `core.games`
  (`db/models/core.py:180-240`) has no lineage. The 85 MB includes
  `created_at`/`updated_at`, which would stay, and dropped columns are not
  returned to the OS without a table rewrite — the real saving is unmeasured.
- Current head: `0012_ml_predictions`.

# Human decisions or resources

- [x] **H-09: deferred** (2026-11-15: the owner said "start the task" after
      these recommendations were presented; each is taken as the decision) —
      not in this card; `(H-09 only)` items below do not
      apply. Recommended: **defer it** to its own card. It is the part that
      widens the migration most: data-restoring downgrade, loader and repository
      changes for both game loaders, a cross-table consistency rule, and a saving
      that is unmeasured. H-07 and H-12 are independent of it. If it is kept: move
      `source_url`, `cache_path`, `parser_version` to `core.games` (set for
      `final`, NULL otherwise, enforced by `CHECK`), drop them from both game
      stats tables, and add the H-09 items marked below. Adds about 3–4 h.
- [x] **Key grammar: as recommended.** The path of the file actually read, relative
      to `SCRAPER_CACHE_DIR`, with `/` separators, matching
      `^[a-z0-9][a-z0-9._-]*(/[A-Za-z0-9][A-Za-z0-9._-]*)*\.html\.gz$` — no empty
      segment, no `.` or `..` segment, no drive letter, no leading `/`, no `\`.
      The same grammar is a `CHECK` on every `cache_path`.
- [x] **Column name: kept.** Keep `cache_path`, change only its meaning.
      Renaming to `cache_key` touches the app-owned `UNPUBLISHED_COLUMNS`.
- [x] **Constraint set (H-12): as recommended**, on the 4 totals tables: every
      counting column `>= 0`; `gs <= g`; `fg <= fga`, `fg2 <= fg2a`,
      `fg3 <= fg3a`, `ft <= fta`; `fg_pct`, `fg2_pct`, `fg3_pct`, `ft_pct` in
      [0, 1]; `efg_pct` in [0, 1.5]; each check true when its columns are NULL.
      Plus `NOT NULL` on `core.players.basketball_reference_player_id`. Not
      included: domain checks on `source_team_code`, `seasons.league`,
      `season_year`.
- [x] **Optional audit items #13, #14, #16: left out.**

# Acceptance criteria

Items marked *(H-09 only)* do not apply (H-09 deferred).

**Key and producers**

- One helper relativises the path a producer actually read against the cache
  root and returns a key matching the grammar; every producer listed in
  Evidence stores its result. It never substitutes `path_for_url(url)` for the
  file that was read.
- Absolute or relative explicit inputs to `offline_processor` still work; the
  stored key is relative either way. Tests: absolute `SCRAPER_CACHE_DIR`;
  explicit absolute input; `fixture.html.gz` directly under the root.
- Negative tests: the helper and the `CHECK` both reject `C:\…`, `/…`, `\`,
  `..`, `./`, empty segments, a path outside the root, and a non-`.html.gz`
  name.
- When the source is a URL, a test asserts the stored key equals the canonical
  `path_for_url(url)` key, so a URL/file mismatch is detectable.

**Migration `0013`**

- Rewrites existing values by stripping everything up to and including the
  cache root marker (`data/raw/html/` after normalising `\` to `/`), then checks
  every result against the grammar. Taking "the last two components" is not
  acceptable: it can collapse different subdirectories.
- For rows whose `source_url` is a Basketball Reference URL, the migration (or
  the preflight) reports how many rewritten keys differ from the canonical key
  of that URL; any difference blocks the upgrade unless the card's review
  records why it is legitimate.
- **Fails closed:** aborts with table and count, changing nothing, on any key
  that does not reduce cleanly, any NULL player id, or any existing row that
  violates a new `CHECK`.
- Constraint text in models and revision is pinned together by a test.
- `downgrade()` restores schema exactly; it cannot restore the original absolute
  paths and its docstring says so. *(H-09 only:)* before dropping the
  `core.games` columns it copies lineage back into both game stats tables and
  only then restores `NOT NULL`.

**Validator and preflight**

- `official_stats.py` bounds `efg_pct` to [0, 1.5] and keeps `ts_pct` at its
  current range; tests cover both bounds, just outside them, and NULL
  (historical absences stay valid).
- `preflight_migration_data.py` gains `check_0013_precondition`: invalid or
  unreducible paths, URL/key mismatches, NULL player ids, rows violating each
  new `CHECK`; *(H-09 only:)* `final` games whose box-score rows have no lineage,
  and games whose rows disagree after normalisation across **both**
  `team_game_totals` and `player_game_totals`. Unit tests per failure kind.
- A failed upgrade on a disposable database leaves data, schema and
  `alembic_version` unchanged (test).

**Round trip with data**

- A new integration test populates a disposable database at `0012` with wide
  rows in both legacy formats, games and box scores, upgrades, checks values,
  downgrades, checks values and `created_at`/`updated_at`, and upgrades again.
  `validate_postgres_local.py`'s catalog comparison stays as is.
- Reloading the same cache after upgrade reports the game loader's `unchanged`
  status.

**General**

- Ruff, mypy, the full offline suite, the PostgreSQL integration lane, and
  `scripts/validate_tasks.py --all-worktrees` pass.

# Scope

- `alembic/versions/0013_*.py`; `db/models/stats.py`, `db/models/core.py`.
- The key helper in `scraping/cache.py`, and every producer in Evidence.
- `validation/official_stats.py` (efg bound, lineage rules).
- `scripts/preflight_migration_data.py` and its tests.
- A populated round-trip integration test.
- *(H-09 only)* `loaders/games.py`, `loaders/current_season_games.py`,
  `db/repositories/games.py`.
- Docs: `OFFICIAL_STATS_SCHEMA.md`, `BUSINESS_RULES.md`,
  `MIGRATION_HEAD_HANDOVER.md` (deployment sequence), the audit's resolution
  table.

# Out of scope

- Applying `0013` to `nba` (owner instruction; see `critical_actions`).
- Audit items #13, #14, #16 and, unless chosen, H-09.
- Moving or renaming cache or snapshot files.
- Any API code change.
- Live acquisition.

# Impact

- Tables: 32 wide `stats` tables and the roster (rewrite + format `CHECK`); the
  two game stats tables (rewrite + format `CHECK`, or H-09 move); the 4 totals
  tables (`CHECK`s); `core.players` (`NOT NULL`).
- Commands: every `nba-data backfill …`, both current-season loads,
  `validate official-stats`, `validate offline-database`, the migration
  preflight.
- **Deployment sequence** (to record in `MIGRATION_HEAD_HANDOVER.md`):
  1. merge to `main`; 2. stop the API and any loader/refresh (the API would
  answer 503 anyway; an old loader would violate the new `CHECK`);
  3. verified backup; 4. `preflight_migration_data.py --revision 0013`;
  5. `alembic upgrade head` from `origin/main`; 6. `validate offline-database`
  and `validate official-stats`; 7. `VACUUM (ANALYZE)` of rewritten tables;
  8. restart the API, check `/health/ready`. Recovery: on a failed upgrade the
  transaction rolls back and `nba` stays at `0012`; on a bad result after
  commit, restore the backup.
- Disk: *(H-09 only)* logical row size of `player_game_totals` drops; physical
  space is not returned without a rewrite (`VACUUM FULL`/`pg_repack`, out of
  scope). Measure before and after; claim no figure in advance.

# Cross-track impact

- None.

# Implementation notes

- Key helper: `relative_cache_key(path: Path, root: Path) -> str` — resolve
  both, require `root in path.parents`, return `path.relative_to(root).as_posix()`,
  validate against the grammar.
- Constraints: plain `ADD CONSTRAINT` (validated on add) so existing violations
  abort the upgrade; the preflight reports them first.
- Keep `0013` in one transaction (PostgreSQL DDL is transactional) so a failure
  leaves `nba` at `0012`.

## Implementation record (2026-11-15)

- **`NOT NULL` deferred to F8-025.** With it, 25 app-track unit tests
  (`test_player_api.py`, `test_player_query_repository.py`) failed: they seed a
  player with a NULL id to prove the API's filter. Fixing them is `shared` work,
  so `0013` leaves the column, the model and `player_page_acquisition.py` as
  they were. The preflight's refusal list has 51 counts, not 52.
- **Revision id** is `0013_portable_lineage_checks`: Alembic's
  `alembic_version.version_num` is `varchar(32)` and the planned name was 39.
- **Grammar module** is `nba_data/domain/cache_key.py`, not under `db/`:
  `validation/stats_coverage.py` must not import `nba_data.db`
  (`tests/unit/test_stats_coverage_artifact.py`).
- **Key grammar** allows an upper-case letter at the start of the first segment
  too (one segment pattern for all segments). Every rejection the card lists
  still holds.
- **The key `CHECK` is PostgreSQL-only** (`ddl_if(dialect="postgresql")`):
  SQLite unit-test schemas have no `~`. `require_cache_key` guards every write
  in Python on every dialect.
- **URL/key agreement is checked by the preflight,** not inside the migration
  (the canonical key needs `HtmlCache`'s slug and hash).
- **Pins** live in `tests/unit/test_cache_key.py` (pattern, check text, table
  lists, model constraints), not `test_stats_models.py`.
- Test fixtures that stored placeholder paths (`boxscores/probe.html`, absolute
  fixture paths) now store valid keys.

### Review fixes (2026-11-15)

- **Forward-slash root paths.** `data/raw/html/basketball-reference/x.html.gz`
  already matched the key grammar, so the first version of `0013` kept it
  unchanged (and the preflight would then have blocked on the URL mismatch).
  The rewrite now applies to every value that contains `data/raw/html/`,
  grammar match or not; a value without it is kept. The refusal and the
  preflight's `stored_key_after_0013` follow the same rule. `nba` had no such
  value (preflight still passes, 82,027 pairs).
- **Validator matches the new checks.** `validate official-stats` reports
  makes greater than attempts (fg/fg2/fg3/ft) under `impossible_numeric_values`
  and a `cache_path` that is not a key as `invalid_cache_key`
  (`invalid_cache_key_rows` in the summary). Until `0013` is applied, `nba`
  fails the latter on its legacy paths, as intended.
- **Reload idempotency across the migration** is now tested on PostgreSQL:
  `test_a_cached_game_reloads_unchanged_after_0013` loads a game, sets its rows
  to the two legacy shapes by SQL, upgrades, and reloads the same fixture:
  `unchanged`, no new players, same ids, keys and `updated_at`.

# Estimated effort

- H-07 + H-12 with the work above (preflight, validator, populated round trip,
  deployment doc): about 6–8 h.
- With H-09: about 9–12 h.
- Applying to `nba`: about 20–40 min of the owner's time, writers paused.

# Durable knowledge updates

- `OFFICIAL_STATS_SCHEMA.md`, `BUSINESS_RULES.md`: meaning and grammar of
  `cache_path`; the totals constraints; the `efg_pct` bound.
- `MIGRATION_HEAD_HANDOVER.md`: the `0013` sequence.
- `DATABASE_AUDIT_2026-11-10.md`: H-07 and H-12 (and H-09 if chosen) resolved by
  F8-024.

# Review evidence

## Final review (2026-11-15)

- Rechecked the complete working-tree change against local `origin/main` and
  the acceptance criteria. No remaining major findings in scope. The earlier
  forward-slash migration, validator consistency, and post-upgrade reload
  findings are covered by implementation and regression tests.
- Focused unit command from `validation:`: 354 passed.
- `uv run pytest -q`: 2034 passed, 314 skipped, 7 deprecation warnings.
- `uv run python scripts/validate_postgres_local.py`: exit 0; 315 passed,
  exact head downgrade catalog restoration, no new Alembic operations, and
  scratch database removed. Docker Desktop was started after the initial
  attempt could not connect; the persistent database was not migrated.
- `uv run ruff check .`: passed. `uv run mypy src/nba_data`: passed for
  118 source files. `git diff --check`: passed.
- Corrected stale preflight and audit descriptions: 0013 does not require
  non-null public player ids; F8-025 retains that deferred work.
- The owner explicitly requested moving the card to `done` if the final review
  found no major issues. No cross-track entries target F8-024 and no parked
  card bookkeeping applies. No Git staging, commit, push, or PR creation was
  requested.

## Automated validation

- Command: `uv run pytest` (focused unit files from `validation:` first)
- Result: 2034 passed, 314 skipped (integration tests skip offline), after the
  review fixes.
- Command: `bash scripts/validate_database.sh`
- Result: exit 0. Head round trip: "The head revision's downgrade exactly
  restored 0012_ml_predictions."; `alembic check`: "No new upgrade operations
  detected."; integration lane 315 passed, including
  `test_lineage_migration_postgres.py` (rewrite of the legacy formats with
  timestamps unchanged; up, down, up; refusal leaves data, schema and
  `alembic_version` unchanged; the post-upgrade `CHECK` rejects machine paths
  and `efg_pct` 1.51; a cached game reloads `unchanged` after the upgrade).
- Command: `uv run ruff check .` — All checks passed.
- Command: `uv run mypy src/nba_data` — no issues in 118 source files.
- Command: `uv run python scripts/validate_tasks.py --all-worktrees` — passed.
- Command: preflight `--revision 0013_portable_lineage_checks` against `nba`,
  read-only (`postgresql_readonly`), 2026-11-15 — "51 refusal counts checked",
  "82027 distinct (source_url, cache_path) pairs compared", passed.
  `alembic current` on `nba` afterwards: `0012_ml_predictions` (not applied).
- Read-only queries on `nba`: all 832,616 lineage values reduce to a valid key;
  0 totals rows violate any new check; `max(efg_pct)` is exactly 1.5000.

## Manual happy path

1. `uv run pytest tests/unit/test_cache_key.py -q` — grammar, helper and 0013
   pins pass.
2. `bash scripts/validate_database.sh` — exit 0, the `0012` round-trip line is
   printed.
3. `uv run python scripts/preflight_migration_data.py --database-url <nba url>
   --revision 0013_portable_lineage_checks` — passes with 82,027 pairs compared.

Expected result: all three succeed; `nba` stays at `0012`.

## Manual sad path

1. In a scratch database at `0012`, set one `stats.player_season_totals.cache_path`
   to `D:\elsewhere\x.html.gz` and one row's `gs` above `g`.
2. Run the preflight for `0013`, then `alembic upgrade head`.
3. Inspect the rows and `alembic_version`.

Expected result: the preflight exits 1 naming both; the upgrade fails with
"Refusing to apply 0013: ..." listing both counts; nothing changed and the
version is still `0012` (automated in
`test_0013_refuses_and_changes_nothing_when_data_violates_it`).

## Known limitations

- H-12 is only partly resolved; the `NOT NULL` is F8-025 (`shared`).
- H-09 is deferred and has no card yet.
- `downgrade()` cannot restore the original absolute paths.
- The rewrite leaves a dead version of every rewritten row until
  `VACUUM (ANALYZE)` (step 7 of the handover sequence).
