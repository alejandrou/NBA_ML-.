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

Each command writes its full JSON report to `--output` and prints a compact
summary to the terminal, even when it exits with code `1`. Read the written file
for the full report. An exit code of `1` means that the producer reported failed entries, failed or
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
across every `stats.*` table.

Two Phase 4E baselines exist, and they are not interchangeable:

| Baseline | Team-season | Regular player | Postseason aggregate | Postseason stint | Total |
|---|---|---|---|---|---|
| `-v1` archive, as loaded in 2026-08 | 129,000 | 96,336 | 40,528 | 40,528 | 306,392 |
| `-v4` rebuild, measured 2026-08-28 | 129,000 | **101,336** | **42,408** | **42,408** | **315,152** |

The `-v1` row is what a database still carrying the original player-page load
reports. The `-v4` row is what a full cache-only rebuild under the current parser
contract produces, measured on a scratch database in the F4E-024 rehearsal. Use
the row that matches the `parser_version` the database actually carries; a
database at `-v1` fails `validate official-stats` on lineage regardless of its
row counts.

The old `--stats-backfill-report` option is removed. Use the three typed options
above; a partial set is reported as incomplete rather than accepted as a full
archive reconciliation.

### Producer exit codes on a complete rebuild

Both player-page producers exit **0** on a complete cache-only rebuild. Their
reports distinguish genuinely unresolved in-scope rows from cached rows for
seasons the archive does not load:

| Producer | `entries_failed` | `rows_failed` | In-scope unresolved counter | Out-of-scope counter | Exit |
|---|---|---|---|---|---|
| `backfill stats` | 0 | 0 | — | — | 0 |
| `backfill player-stats` | 0 | 0 | `unresolved_players_or_seasons` = 0 | `out_of_scope_players_or_seasons` = 19,692 | 0 |
| `backfill player-postseason-stats` | 0 | 0 | `unresolved_players_or_seasons_or_team_stints` = 0 | `out_of_scope_players_or_seasons_or_team_stints` = 20,280 | 0 |

A cached player page carries a player's whole career, so the cache spans season
end years **1983–2026**, while `core.seasons` holds only **2000–2025**. The
producers compare each unresolved loader entry's season year with the NBA years
present in `core.seasons` before interpreting its loader reason. Rows outside
that database scope are counted in `out_of_scope_players_or_seasons` or
`out_of_scope_players_or_seasons_or_team_stints`; rows inside the scope remain
in the corresponding `unresolved_*` counter. The measured out-of-scope counts
are exactly the coverage artifact's expectations — 19,692 regular aggregate
rows, and 10,140 postseason aggregate plus 10,140 postseason stint rows.

Read `entries_failed`, `rows_failed`, and the in-scope unresolved counter before
reacting to the exit code. The out-of-scope counter is diagnostic and does not
fail the run. Any nonzero failed-entry, failed-row, or in-scope unresolved
counter still fails the producer.

Because the scope is read from `core.seasons`, an out-of-scope row is classified
by its season whatever its loader reason — a player who only ever appeared
before 2000 is out of scope, not missing. That would otherwise hide a genuinely
absent player, so each report also carries `out_of_scope_reason_counts`, the
loader reasons behind the out-of-scope total. On a complete rebuild the total is
`missing_season`; a `missing_player` entry there means a cached page whose player
never reached the archive's season range.

Running either producer against an empty `core.seasons` would classify every
cached row as out of scope and report a success that loaded nothing, so both
refuse to start: they abort with `EmptySeasonScopeError` and a nonzero exit
before processing any page. Run `backfill offline` first.

The rehearsal driver applies the same contract: any nonzero producer exit stops
the rebuild, with no exception for out-of-scope rows.

### Row-level coverage (F4E-018)

Report totals reconcile even when one missing key happens to be offset by one
unexpected key. Build the independent, cache-derived coverage artifact
(F4E-017) and pass it to `validate official-stats` to catch that case by name:

```bash
uv run nba-data validate build-stats-coverage --output reports/stats-coverage.json

uv run nba-data validate official-stats \
  --team-stats-report reports/stats-backfill-2000-2025.json \
  --player-stats-report reports/player-stats-backfill-2000-2025.json \
  --player-postseason-stats-report reports/player-postseason-stats-backfill-2000-2025.json \
  --coverage-artifact reports/stats-coverage.json
```

That runs the comparison **unverified**: it trusts the artifact's own claims
about the cache without re-reading it, and `coverage_summary.freshness_status`
reports `unverified` in the JSON output. To also confirm the artifact still
matches the live cache before trusting it, add `--coverage-cache-root`:

```bash
uv run nba-data validate official-stats \
  --coverage-artifact reports/stats-coverage.json \
  --coverage-cache-root "$SCRAPER_CACHE_DIR"
```

A fingerprint mismatch fails with `coverage_artifact_stale` and skips key
comparison rather than risk comparing against a cache that has since changed.

Coverage failure codes, one per situation:

| Code | Meaning |
|---|---|
| `coverage_artifact_missing` | `--coverage-artifact` was not given; the rest of the report still ran. |
| `coverage_artifact_schema_unsupported` | The artifact's `schema_version` is not one this validator understands. |
| `coverage_artifact_invalid` | The artifact's JSON shape is malformed. |
| `coverage_cache_root_not_found` | `--coverage-cache-root` does not exist. |
| `coverage_artifact_stale` | The recomputed cache fingerprint does not match the artifact's. |
| `coverage_unexplained_source` | The artifact itself has cached seasons it could not classify. |
| `coverage_scope_empty` | `core.seasons` has no rows for the NBA league, so the coverage comparison has no trustworthy season scope. |
| `coverage_source_issues_present` | The artifact has unreadable/malformed cached sources — a degraded oracle. |
| `coverage_missing_<dimension>_row` / `coverage_unexpected_<dimension>_row` | A natural key the artifact expects is absent from `stats.*`, or `stats.*` has one the artifact does not expect, for `regular_aggregate`, `postseason_aggregate`, `regular_team_stint`, or `postseason_team_stint`. |

## Rebuilding the Player-Page Archive at `-v4`

F4E-013, F4E-014 and F4E-022 each fixed a player-page selection defect, and
F4E-025 made parser lineage an enforced contract. None of those cards ran a
backfill, so a database loaded before them carries `player-page-parser-v1` rows
that both miss recoverable player-seasons and fail lineage validation outright.
This section is the rebuild that resolves both.

### What the rebuild recovers

Measured on a scratch database, 2026-08-28, from the 2,551 cached player pages:

| Grain | Before (`-v1`) | After (`-v4`) | Change |
|---|---|---|---|
| Distinct regular-season player-seasons | 12,042 | **12,667** | **+625** |
| Distinct postseason player-seasons | 5,066 | **5,301** | **+235** |
| Distinct postseason team stints | 5,066 | **5,301** | **+235** |
| Distinct team-season stints | 14,332 | 14,332 | 0 |

The 625 recovered regular-season player-seasons decompose exactly against the
archive audit, with nothing unclassified and **nothing lost**:

| Bucket | Count | Fixed by |
|---|---|---|
| Season 2000 century rollover | 439 | F4E-013 |
| 36 players with 6- or 7-character ids | 184 | F4E-012 |
| `jonesbo02` 2008 (`5TM` marker) | 1 | F4E-014 |
| `milleol01` 2004 ("Did not play" placeholder) | 1 | F4E-022 |
| **Total** | **625** | |

The 9 postseason-only seasons — `adamsja01` 2020, `hollajo02` 2016, `jeffrda01`
2023, `jonesdw02` 2013, `lawsoty01` 2018, `mcgratr01` 2013, `thomptr01` 2023,
`vildolu01` 2022, `wrighdo01` 2016 — correctly keep **0** regular-season
aggregate rows and 8 postseason rows each. They are correct as loaded and must
not be "recovered".

### Rehearsing on a scratch database

Never rehearse in place. The rehearsal driver creates a uniquely named scratch
database, migrates it to head, runs the four backfills and both validators
against it, captures the grain evidence, and drops it in a `finally` path:

```bash
uv run python scripts/dev/rehearse_player_page_rebuild.py
```

It refuses to run any backfill whose `DATABASE_URL` resolves to the configured
database, and refuses to drop anything outside its `nba_f4e024_tmp_` prefix. It
sets `DATABASE_URL` in each child process rather than in `.env`, because
`get_settings()` is `@lru_cache`d and an in-process change after the first call
is ignored.

Build the coverage artifact separately and concurrently — it is database-free
and takes about 45 minutes, so running it alongside the backfills saves that
time:

```bash
uv run nba-data validate build-stats-coverage --output reports/stats-coverage.json
```

Expect roughly 70 minutes end to end: offline backfill ~9 min, team-season stats
~18 min, player regular-season stats ~22 min, player postseason stats ~21 min.

### The order matters

Run `backfill offline` first and confirm the core counts before concluding
anything about stats numbers. The player-page backfills resolve grains against
`core.players`, `core.seasons` and `core.player_seasons`; a database seeded with
anything less than the full offline backfill can leave in-scope rows in the
`unresolved_*` counters instead of recovering them. Rows outside the database
season scope are reported separately, and a completely unseeded `core.seasons`
aborts the producer rather than reporting every row as out of scope. The expected core counts are
`core.players` 2,551, `core.player_seasons` 12,676, `core.player_team_seasons`
14,344.

### Upsert-only leaves no residue — F4E-024 observed measurements

`StatsRepository` exposes only `upsert_*` methods; there is no delete in the
stats write path. A re-run therefore updates rows the new parser still selects
and inserts the recoveries, but cannot remove a row the new parser no longer
produces. The pre-F4E-029 coverage comparison settled whether any such row
existed. The following values were measured during the F4E-024 rehearsal before
season scoping was added; the full-cache artifact supplied the out-of-archive
expectations:

```text
regular_aggregate      expected 121,028  actual 101,336  unexpected 0
postseason_aggregate   expected  52,548  actual  42,408  unexpected 0
regular_team_stint     expected 129,000  actual 129,000  unexpected 0
postseason_team_stint  expected  52,548  actual  42,408  unexpected 0
```

**`unexpected` was 0 in all four dimensions**, and an independent before/after
diff of the regular-season grain keys found 625 recovered and **0 lost**. The
upsert-only rebuild strands nothing according to that measured pre-scope run.
No delete step is needed based on that evidence, and no card should add one on
speculation.

### F4E-029 projected comparison — not yet observed end to end

F4E-029 changes only the expected side of the comparison. The following target
is derived arithmetically from the measured F4E-024 artifact and the
2000–2025 NBA scope; it is **expected, not a new measured result**:

```text
dimension               expected after scope  actual observed  projected missing  observed unexpected
regular_aggregate                 101,336          101,336                  0                    0
postseason_aggregate               42,408           42,408                  0                    0
regular_team_stint                129,000          129,000                  0                    0
postseason_team_stint              42,408           42,408                  0                    0
```

The expected and projected-missing columns are arithmetic predictions, not
output from a post-F4E-029 `validate official-stats` run. The actual and
unexpected columns are retained observations from the F4E-024 rehearsal.

### F4E-029 scope behavior — implementation complete, measurement pending

`build-stats-coverage` still records every season on every cached player page —
1983 through 2026 — because the artifact is a faithful, database-free record
of the cache. `validate official-stats` now compares its expected keys only for
NBA season years present in `core.seasons`. The implemented comparison is
expected to produce the projected target above when run against the F4E-024
rebuild, but that end-to-end rerun has not happened yet.

The JSON report keeps the scope visible under each
`coverage_summary.dimensions.<dimension>.scope`: it includes the league, loaded
season years, artifact entries in and out of scope, excluded season years, the
number of excluded expected keys, and the reason
(`season_not_loaded_for_league`). An empty NBA scope is a hard
`coverage_scope_empty` finding; it cannot pass vacuously. Actual persisted keys
are filtered to NBA seasons to prevent a same-year non-NBA row from satisfying
an NBA expectation, but are not filtered to the artifact's expected keys, so a
valid NBA row with no artifact expectation is still reported as unexpected.

Until the end-to-end rerun is recorded, do not describe the projected table as
an observed exit-0 result. For the already measured F4E-024 run, use
`parser_lineage_violations`, the four observed `unexpected` counts, the measured
grain counts, and the producer failure counters to judge residue; its exit 1 is
explained by the pre-fix unscoped comparison. After F4E-029 is rerun, accept
the validator only when it actually exits 0 with all four `missing` and
`unexpected` counts at 0.

The producer counters now have a stable distinction: with
`entries_failed = 0` and `rows_failed = 0`, `unresolved_*` counts only rows whose
season is present in the NBA `core.seasons` scope, while the matching
`out_of_scope_*` field records cache rows outside it. Out-of-scope counts do not
fail the producer; any nonzero failed-entry, failed-row, or in-scope unresolved
counter does. The rehearsal driver stops on any nonzero producer exit, so it no
longer needs a report-reading exception for these diagnostic rows.

The lineage half of the F4E-024 measured run is clean:
`parser_lineage_violations` is **0**,
and `select distinct parser_version` across all 33 `stats` tables returns exactly
three values — `team-season-parser-v1`, `player-page-parser-v4`, and
`player-page-postseason-parser-v4`. `coverage_summary.freshness_status` reports
`verified`, with `unexplained_count` and `source_issues_count` both 0.

### Handover: running the rebuild against the persistent `nba` database

**This procedure requires the owner's direct, current instruction naming the
operation and its scope. No card authorizes it, and the F4E-024 rehearsal
explicitly did not perform it.**

Preflight, in order:

1. **Close the migration gap.** `nba` reports `alembic_version =
   0006_synthetic_team_codes`; the head is `0007_team_bref_id_not_null`. The
   rehearsal ran at head. Applying `0007` to `nba` is itself a critical action
   needing its own approval.
2. **Re-rehearse if the head moved.** F4E-020 and F4E-021 introduce `0008` and
   `0009`. Neither touches a `stats` table, but if either has landed, re-run the
   rehearsal at the new head before trusting these numbers.
3. **Capture the lineage baseline.** Record `select parser_version, count(*)`
   across the player-page stats tables before starting. It is the only evidence
   that will later show what changed.
4. **Back up.** The write path is upsert-only and the rehearsal found no residue,
   but a rebuild that touches 177,392 rows deserves a restore point.
5. **Confirm the cache is unchanged** — 2,551 player pages, 775 team-season
   pages — and rebuild the coverage artifact if it is not.

Then run, against `nba`, the same commands the rehearsal ran, in this order:

```bash
uv run nba-data backfill offline  --execute-approved-backfill              --output reports/offline-backfill.json
uv run nba-data backfill stats    --execute-approved-stats-backfill        --output reports/stats-backfill-2000-2025.json
uv run nba-data backfill player-stats --execute-approved-player-stats-backfill --output reports/player-stats-backfill-2000-2025.json
uv run nba-data backfill player-postseason-stats \
  --execute-approved-player-postseason-stats-backfill \
  --output reports/player-postseason-stats-backfill-2000-2025.json
```

Accept the run only if it reproduces the measured producer/grain shape and the
post-F4E-029 validator result: `entries_failed` 0 and `rows_failed` 0 from
every producer, 101,336 regular and 42,408 + 42,408 postseason rows loaded,
12,667 distinct regular-season player-seasons, all four `missing` and
`unexpected` counts 0, `parser_lineage_violations` 0, and an actual validator
exit code of 0. Until that rerun, the scoped expected counts remain projections
and are not acceptance evidence. Stop and investigate on any other shape — in
particular, a nonzero `unexpected` count would mean the rebuild needs a delete
step, which is a different change with a different blast radius.

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
