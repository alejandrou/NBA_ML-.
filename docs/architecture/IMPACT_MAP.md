# Impact Map

Answers one question: **if I change this, what else must I check?**

This is a hand-maintained index, not an architecture document. For what the
layers are and why they exist, read `docs/architecture/SYSTEM_DESIGN.md`. For
domain rules, `docs/domain/BUSINESS_RULES.md`.

Load this when a task spans more than one area or its blast radius is unclear.
A small, single-file task does not need it. Update it in the same card that
changes a flow.

## Areas

| Area | Lives in | Changing it also touches |
|---|---|---|
| `api` | `src/nba_data/api/` | `API_CONTRACT.md`, `API_ARCHITECTURE.md`, `tests/unit/test_api_*.py` |
| `database-read` | `src/nba_data/db/repositories/queries/` | API services, request session lifecycle |
| `database-schema` | `src/nba_data/db/models/`, `alembic/versions/` | `db/models/__init__.py`, `alembic/env.py`, repositories, validators |
| `scraping` | `src/nba_data/scraping/` | the cache filename contract, discovery regexes, loaders |
| `data-quality` | `src/nba_data/validation/` | `BUSINESS_RULES.md`, the matching backfill report shape |
| `testing` | `tests/` | `docs/validation/TESTING_STRATEGY.md`, pytest markers |
| `documentation` | `docs/`, `AGENTS.md`, `.agents/` | `.agents/index.md` routing rows |
| `planning` | `tasks/planning/` | `scripts/validate_tasks.py`, `tasks/TEMPLATE.md` |

## The only entry point

```bash
uv run nba-data <group> <command>
```

Declared at `pyproject.toml [project.scripts]` as `nba_data.cli.main:app`. There
is **no** `src/nba_data/__main__.py`, so `python -m nba_data` silently does
nothing. Every command below lives in `src/nba_data/cli/main.py`.

## Cross-cutting couplings

These break silently. Check them whenever you touch the cache or the stats
schema.

1. **The cache filename shape is a contract with three separate regexes.**
   `HtmlCache.path_for_url` (`src/nba_data/scraping/cache.py`) produces
   `{root}/{host_dir}/{slug}-{sha256(url)[:16]}.html.gz`. That shape is
   re-derived, not imported, by:
   - `scraping/cache_inventory.py` — `_CACHE_TEAM_SEASON_FILE_RE` (strict)
   - `scraping/cache_inventory.py` — `_TEAM_SEASON_LIKE_FILE_RE` (loose)
   - `scraping/player_page_cache.py` — `_PLAYER_CACHE_FILE_RE`

   Change the slug, the digest length, or the extension and discovery silently
   returns zero entries instead of failing.

2. **Player-id length is shared across the acquire/discover boundary.**
   `PLAYER_ID_PATTERN` in `domain/player_id.py` (`[a-z][a-z0-9]{5,9}`, 6-10
   characters) is the one definition — a dependency-free leaf, like
   `domain/team_codes.py`, so a pure consumer can use it without pulling in
   SQLAlchemy or the scraping client. `scraping/player_page_acquisition.py`'s
   `_PLAYER_ID_RE` and `scraping/player_page_cache.py`'s
   `_PLAYER_CACHE_FILE_RE` both interpolate it rather than restating a range.
   Widen or narrow the accepted id there and all three ends move together;
   restate it anywhere else and the drift F4E-012 fixed comes back.

3. **Both player-page backfills, and the cache-derived stats-coverage
   builder (F4E-017), share one discovery contract.**
   `scraping/player_page_cache.py` holds
   `resolve_player_cache_root`, `discover_player_cache_entries`,
   `discovery_status_for`, `read_cached_gzip`, and `required_html` — pure, no
   database or HTTP import, so `validation/stats_coverage.py` can import it
   too. `scraping/offline_player_postseason_stats_backfill.py` still imports
   the private `_validate_inputs` from
   `scraping/offline_player_stats_backfill.py` (F4E-027 tracks closing that
   one remaining private cross-import). Any change to the shared module
   changes both backfills and the coverage builder together.

4. **`Settings.scraper_cache_dir` defaults to the relative `Path("data/raw/html")`**
   (`src/nba_data/config/settings.py`) and `get_settings()` is `@lru_cache`d.
   Every cache-reading flow resolves it against the process working directory,
   and an env change after the first call is ignored. Both player backfills now
   fail loudly on a missing root (`PlayerCacheRootNotFoundError`, naming the
   resolved path) instead of reporting a successful run over zero pages; the
   other cache-reading flows still do not.

5. **Adding one `stats` table costs six edits:** the model in
   `db/models/stats.py`, the export in `db/models/__init__.py`, an Alembic
   revision chained off `0005_postseason_stats_tables`, membership in the right
   `StatsRepository` model set, a `StatsTableSpec` in
   `validation/official_stats.py`, and the import in `alembic/env.py`.

## Flows

### Team-season acquisition

- **Command:** `acquisition dry-run-nba-team-seasons`;
  `acquisition acquire-nba-team-seasons <START_YEAR> <END_YEAR> --owner-approved --execute-approved-manifest`;
  the generic `backfill dry-run|acquire <MANIFEST_PATH> --execute-approved-manifest`
- **Inputs:** the deterministic team/season catalog; approved manifests under `tasks/manifests/`
- **Implementation:** `scraping/nba_team_season_manifest.py`, `nba_team_season_acquisition.py`, `backfill_manifest.py`, `client.py`, `cache.py`
- **Outputs:** `.html.gz` under `data/raw/html/basketball-reference/`; a JSON report
- **Tables:** none — acquisition never writes database rows
- **Tests:** `test_nba_team_season_manifest.py`, `test_nba_team_season_acquisition.py`, `test_backfill_manifest.py`, `test_rate_limited_client.py`, `test_html_cache.py`
- **Docs:** `docs/validation/NBA_TEAM_SEASON_CACHE_ACQUISITION.md` (record of the completed 2000-2025 run)
- **Critical actions:** contacts Basketball Reference — needs the user's direct, current instruction
- **Invariants:** 10 requests/minute default, hard cap 20, at least 6 seconds apart, honor `Retry-After`, stop on 429, never overwrite a cache file, both approval flags required

### Offline processing

- **Command:** `backfill offline --execute-approved-backfill [--max-workers N] [--output PATH]`
- **Inputs:** cached team-season HTML only
- **Implementation:** `cache_inventory.py` → `offline_backfill.py` → `offline_processor.py` → `offline_loader.py` → `loaders/team_season.py`; reporting via `offline_reporting.py`
- **Outputs:** `core` rows; a JSON backfill report
- **Tables:** `core.seasons`, `teams`, `team_aliases`, `team_seasons`, `players`, `player_seasons`, `player_team_seasons`
- **Tests:** `test_cache_inventory.py`, `test_offline_backfill.py`, `test_offline_processor.py`, `test_offline_loader.py`, `test_offline_reporting.py`, `test_team_season_loader.py`, `tests/integration/test_team_season_loader_postgres.py`
- **Docs:** `docs/validation/OFFLINE_DATABASE_PREPARATION.md`, `docs/validation/TEAM_SEASON_PIPELINE.md`
- **Critical actions:** writes rows to a real database
- **Invariants:** cache-only, never network; loaders idempotent on natural keys; the caller owns the transaction

### Official stats validation

- **Command:** `validate offline-database --backfill-report <PATH>`;
  `validate official-stats [--team-stats-report <PATH>]`
  `[--player-stats-report <PATH>]`
  `[--player-postseason-stats-report <PATH>]`
  `[--coverage-artifact <PATH>] [--coverage-cache-root <PATH>]`;
  `validate build-stats-coverage --output <PATH> [--cache-root <PATH>]`
- **Inputs:** the database plus the JSON report from the matching backfill;
  `official-stats` optionally also takes the F4E-017 stats-coverage artifact
  (built by `build-stats-coverage` from cached HTML, database-free)
- **Implementation:** `validation/offline_database.py`, `validation/official_stats.py`, `validation/team_season.py`, `validation/stats_coverage.py`
- **Outputs:** a findings report; non-zero exit on failure
- **Tables:** reads `core` and `stats`; writes nothing
- **Tests:** `test_offline_database_validation.py`, `test_official_stats_validation.py`, `test_team_season_validation.py`, `test_stats_coverage_artifact.py`
- **Docs:** `docs/architecture/OFFICIAL_STATS_SCHEMA.md` (large — open on demand), `docs/validation/OFFLINE_DATABASE_PREPARATION.md`
- **Critical actions:** none; read-only
- **Invariants:** `TOT` is never a real team; a multi-team marker (any team count of at least two followed by `TM`) is an aggregate source marker, not a team; regular season and postseason never mix; row-level coverage (F4E-018) fails on a missing or unexpected natural key even when aggregate report totals reconcile, and does not silently pass when its coverage artifact is missing, unsupported, malformed, or stale

### Player-page acquisition

- **Command:** `acquisition dry-run-player-pages`;
  `acquisition acquire-player-pages --owner-approved --execute-approved-manifest`
  (both accept `--limit`, `--player`, `--start-year`, `--end-year`, `--output`)
- **Inputs:** `core.players.basketball_reference_player_id`, optionally filtered by season through `core.player_seasons`
- **Implementation:** `scraping/player_page_acquisition.py`, `client.py`, `cache.py`
- **Outputs:** player-page `.html.gz` under the cache root; a JSON report
- **Tables:** reads `core`; writes no rows
- **Tests:** `test_player_page_acquisition.py`
- **Docs:** `docs/validation/PLAYER_PAGE_CACHE_ACQUISITION.md`
- **Critical actions:** contacts Basketball Reference — needs the user's direct, current instruction
- **Invariants:** URLs only `https://www.basketball-reference.com/players/{initial}/{player_id}.html`; cache-first; never overwrite; sequential; resumable; stop on 429 with a partial report. Couplings 1, 2, and 4 apply.

### Regular-season player stats

- **Command:** `backfill player-stats --execute-approved-player-stats-backfill [--limit N] [--player ID] [--start-year YYYY] [--end-year YYYY] [--parser-version V] [--output PATH]`
- **Inputs:** cached player pages discovered from the cache root
- **Implementation:** `offline_player_stats_backfill.py` → `parsers/player_page.parse_player_page_regular_season` → `normalizers/player_page.normalize_player_page_regular_season` → `loaders/player_page_stats.load_player_page_stats` → `StatsRepository`
- **Outputs:** `stats` rows; a JSON report carrying `cache_root` and `discovery_status` (`ok` / `no_matching_pages`)
- **Tables:** the eight `stats.player_season_*` tables and the `stats.player_team_season_*` family
- **Tests:** `test_offline_player_stats_backfill.py`, `test_player_page_parser.py`, `test_player_page_normalizer.py`, `test_player_page_stats_loader.py`, `test_stats_repositories.py`
- **Docs:** `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md`
- **Critical actions:** writes rows to a real database
- **Invariants:** cache-only — this module imports no HTTP client, and a test asserts that. Couplings 1-4 all apply.

### Postseason player stats

- **Command:** `backfill player-postseason-stats --execute-approved-player-postseason-stats-backfill` (same options)
- **Inputs / implementation:** same shape via `offline_player_postseason_stats_backfill.py`, reusing regular-season discovery and validation helpers
- **Tables:** `stats.player_postseason_*` (FK `core.player_seasons.id`) and `stats.player_team_postseason_*` (FK `core.player_team_seasons.id`), added by migration `0005_postseason_stats_tables`
- **Tests:** `test_offline_player_postseason_stats_backfill.py`
- **Docs:** `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md`
- **Critical actions:** writes rows to a real database
- **Invariants:** postseason never merges into regular-season tables. Coupling 3 applies — changing the shared private helpers changes this command too.

### Database

- **Implementation:** `db/base.py`, `db/session.py`, `db/models/{raw,core,stats}.py`, `db/repositories/{core,stats}.py`, `alembic/env.py`
- **Schemas:** `raw` (3 tables), `core` (7), `stats` (33 wide tables in 4
  families — `player_season_*` 8, `player_team_season_*` 9,
  `player_postseason_*` 8, `player_team_postseason_*` 8; 16 of the 33 are
  postseason). There is **no `features` schema yet.**
- **Migrations:** `0001_initial_raw_core` → `0002_core_team_player_season` → `0003_stats_wide_tables` → `0004_player_season_source_team_code` → `0005_postseason_stats_tables`
- **Commands:** `bash scripts/validate_database.sh` (disposable PostgreSQL validation); `uv run python scripts/preflight_migration_data.py --database-url <target>` (read-only `0007` data preflight)
- **Tests:** `test_core_models.py`, `test_raw_models.py`, `test_stats_models.py`, `test_stats_repositories.py`, `tests/integration/test_team_season_loader_postgres.py`
- **Docs:** `docs/architecture/SYSTEM_DESIGN.md` (loader invariants and natural keys), `docs/architecture/OFFICIAL_STATS_SCHEMA.md`
- **Critical actions:** applying a migration to a shared, persistent, or production-like database
- **Invariants:** `raw`, `core`, official `stats`, and future `features` stay separate. Coupling 5 applies.

### FastAPI

- **Implementation:** `api/app.py::create_app` (prefix `/api/v1`; engine and session factory created in `lifespan` and stored on `app.state`), `api/dependencies.py::get_request_session`, `api/routers/`, `api/schemas/`, `api/services/`
- **Inputs / outputs:** PostgreSQL in, public JSON out
- **Tables:** reads only, through `db/repositories/queries/`
- **Tests:** `test_api_foundation.py`, `test_api_session_lifecycle.py`
- **Docs:** `docs/architecture/API_ARCHITECTURE.md`, `docs/architecture/API_CONTRACT.md`
- **Critical actions:** none
- **Invariants:** read-only and GET-only; never uses `CoreRepository`; never returns ORM objects; never creates, commits, or closes its own session; never imports scraping; HTTP tests never require PostgreSQL

### Future: features, metrics, and OVR

- Nothing exists yet: no `features` schema, no `src/nba_data/features/`, no migration, no command.
- **Docs:** `docs/architecture/SYSTEM_DESIGN.md` "Planned Direction", ADR 0008
- **Invariants when it lands:** `features` stays separate from `raw`, `core`, and official `stats`; formula versions are recorded; generation is leakage-safe and never scrapes live.
