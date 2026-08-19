# Offline Database Preparation

This document is the Phase 4D local readiness workflow for preparing PostgreSQL
from already-cached Basketball Reference NBA team-season HTML.

Phase 4D is offline-only after cache acquisition. Do not run live scraping,
refresh cache misses, delete data, run destructive migrations, or start API,
frontend, generated metrics, OVR, ranking, similarity, recommendations, or ML
work as part of this workflow.

API work starts only after Phase 4D is reviewed and approved.

## Start PostgreSQL

```bash
docker compose up -d postgres
```

Use the project defaults unless the owner intentionally overrides environment
settings:

```text
DATABASE_URL=postgresql+psycopg://nba:nba@localhost:5432/nba
SCRAPER_CACHE_DIR=data/raw/html
```

## Apply Migrations

```bash
uv run alembic upgrade head
uv run alembic check
uv run alembic current
```

The expected Phase 4D core database revision is:

```text
0002_core_team_player_season
```

## Confirm Cached HTML Coverage

The Phase 4D acquisition handoff expects 775 cached NBA team-season pages for
Basketball Reference season end years 2000 through 2025.

Run the manifest cache coverage check:

```bash
uv run nba-data acquisition dry-run-nba-team-seasons
```

Expected result after the approved acquisition:

```text
775 cache hits
0 missing cache entries
0 estimated fetches
```

Run the F4D-001 cached HTML inventory from the local cache:

```bash
uv run python - <<'PY'
import json

from nba_data.config.settings import get_settings
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.cache_inventory import build_cached_html_inventory

settings = get_settings()
report = build_cached_html_inventory(cache=HtmlCache(settings.scraper_cache_dir))
print(json.dumps(report.to_dict(), indent=2))
PY
```

Expected inventory counts:

```text
total_discovered_files      775
valid_candidates            775
invalid_or_unreadable_files 0
duplicate_candidates        0
missing_metadata            0
unsupported_paths           0
```

## Run Full Offline Backfill

Run the guarded offline backfill only after the owner has approved Phase 4D
database loading:

```bash
uv run nba-data backfill offline ^
  --execute-approved-backfill ^
  --output reports/offline-backfill-2000-2025.json
```

On Git Bash, use backslashes instead of PowerShell carets:

```bash
uv run nba-data backfill offline \
  --execute-approved-backfill \
  --output reports/offline-backfill-2000-2025.json
```

The command reads existing `.html.gz` files from `HtmlCache`, processes them
through the Phase 4C offline processor, loads validated rows through the
idempotent core loader, and writes a JSON report. It does not scrape, refresh
cache, delete data, or run migrations.

Expected backfill report summary:

```text
selected_inventory_entries 775
skipped_inventory_entries  0
validated_entries          775
failed_entries             0
loaded_entries             775
loaded_rows                129000
quarantined_entries        0
quarantined_rows           0
```

`reports/` is ignored by Git. Keep operational reports local unless the owner
explicitly asks to publish a summarized artifact.

## Run Data Quality Validation

Run the Phase 4D read-only database validation:

```bash
uv run nba-data validate offline-database \
  --backfill-report reports/offline-backfill-2000-2025.json
```

The command exits with code `0` only when the local PostgreSQL core database and
the offline backfill report match the approved Phase 4D readiness baseline.

Expected database counts:

```text
core.seasons                26
core.teams                  37
core.team_aliases           775
core.team_seasons           775
core.players                2551
core.player_seasons         12676
core.player_team_seasons    14344
```

The validation also checks duplicate logical rows, orphan relationships,
team-seasons with no players, suspiciously low per-season counts, `TOT` misuse,
missing Basketball Reference player IDs, and nonzero failure/quarantine counts
from the backfill report.

## Run Official Stats Backfills and Validation

The three stats backfills are separate producers. Run each guarded command from
the local cache when rebuilding the official stats tables:

```bash
uv run nba-data backfill stats \
  --execute-approved-stats-backfill \
  --output reports/stats-backfill-2000-2025.json

uv run nba-data backfill player-stats \
  --execute-approved-player-stats-backfill \
  --output reports/player-stats-backfill-2000-2025.json

uv run nba-data backfill player-postseason-stats \
  --execute-approved-player-postseason-stats-backfill \
  --output reports/player-postseason-stats-backfill-2000-2025.json
```

Each command prints and writes its JSON report even when it exits with code `1`.
An exit code of `1` means that the producer reported failed entries, failed or
quarantined rows, or unresolved player/season grains. Postseason skipped
entries and `unsupported_synthetic_or_tot_rows` are expected and do not fail
the command.

Reconcile all three producer reports against the read-only official-stats
validator in one invocation:

```bash
uv run nba-data validate official-stats \
  --team-stats-report reports/stats-backfill-2000-2025.json \
  --player-stats-report reports/player-stats-backfill-2000-2025.json \
  --player-postseason-stats-report reports/player-postseason-stats-backfill-2000-2025.json
```

When all three reports are supplied, the validator uses each producer's own
row-count vocabulary and requires their combined total to match `count(*)`
across every `stats.*` table. The checked-in Phase 4E baseline contributes
129,000 team-season rows, 96,336 regular player rows, and 40,528 each of
postseason aggregate and team-stint rows: 306,392 rows total.

The old `--stats-backfill-report` option is removed. Use the three typed options
above; a partial set is reported as incomplete rather than accepted as a full
archive reconciliation. The current cached regular player report contains 577
failed entries (including 25,640 rows that partially loaded), so that producer
currently exits nonzero until the placeholder-row fix in F4E-022 is applied.

## Useful SQL Checks

Table counts:

```sql
select 'core.seasons' as table_name, count(*) from core.seasons
union all select 'core.teams', count(*) from core.teams
union all select 'core.team_aliases', count(*) from core.team_aliases
union all select 'core.team_seasons', count(*) from core.team_seasons
union all select 'core.players', count(*) from core.players
union all select 'core.player_seasons', count(*) from core.player_seasons
union all select 'core.player_team_seasons', count(*) from core.player_team_seasons;
```

Team-season coverage by season:

```sql
select
  s.season_year,
  count(ts.id) as team_seasons
from core.seasons s
left join core.team_seasons ts on ts.season_id = s.id
group by s.season_year
order by s.season_year;
```

Player-team rows by season:

```sql
select
  s.season_year,
  count(pts.id) as player_team_seasons
from core.seasons s
left join core.team_seasons ts on ts.season_id = s.id
left join core.player_team_seasons pts on pts.team_season_id = ts.id
group by s.season_year
order by s.season_year;
```

Sample team-season roster shape for future read-only API exploration:

```sql
select
  s.season_year,
  ts.team_abbreviation,
  p.full_name,
  p.basketball_reference_player_id,
  pts.roster_number,
  pts.roster_position
from core.player_team_seasons pts
join core.player_seasons ps on ps.id = pts.player_season_id
join core.players p on p.id = ps.player_id
join core.team_seasons ts on ts.id = pts.team_season_id
join core.seasons s on s.id = ts.season_id
where s.season_year = 2024
  and ts.team_abbreviation = 'BOS'
order by p.full_name
limit 25;
```

Sample player season coverage:

```sql
select
  p.full_name,
  p.basketball_reference_player_id,
  count(ps.id) as loaded_seasons
from core.players p
join core.player_seasons ps on ps.player_id = p.id
group by p.id, p.full_name, p.basketball_reference_player_id
order by loaded_seasons desc, p.full_name
limit 25;
```

Orphan check, expected `0`:

```sql
select count(*)
from core.player_team_seasons pts
left join core.player_seasons ps on ps.id = pts.player_season_id
left join core.team_seasons ts on ts.id = pts.team_season_id
where ps.id is null or ts.id is null;
```

Team-seasons without players, expected `0`:

```sql
select count(*)
from core.team_seasons ts
left join core.player_team_seasons pts on pts.team_season_id = ts.id
where pts.id is null;
```

`TOT` real-team misuse, expected `0`:

```sql
select
  (select count(*) from core.teams
   where basketball_reference_team_id = 'TOT' or current_abbreviation = 'TOT')
  + (select count(*) from core.team_aliases where abbreviation = 'TOT')
  + (select count(*) from core.team_seasons where team_abbreviation = 'TOT')
  as tot_real_team_rows;
```
