# Phase 4D - Full Offline Database Preparation / Backfill Readiness

Status: done
Phase ID: `phase-4d-full-offline-database-preparation`

## Goal

Prepare a real local PostgreSQL database from cached NBA team-season
Basketball Reference HTML before any API phase begins.

Phase 4D now begins with Phase 4D-A, a controlled acquisition subphase that
fills raw `HtmlCache` coverage for NBA team-season pages before inventory,
offline processing, loading, and validation.

The overall Phase 4D flow is:

```text
approved NBA team-season manifest
-> cache-first HtmlCache acquisition
-> cache inventory
-> offline processor
-> idempotent loader
-> PostgreSQL
-> quality checks
-> readiness docs
```

## Preconditions

- Phase 4C is closed after `F4C-001`, `F4C-002`, and `F4C-003` are reviewed and
  marked `done`.
- The Phase 4 SQLAlchemy migration and idempotent loaders are complete.
- The owner has approved Phase 4D-A as a controlled acquisition subphase inside
  Phase 4D.
- Any live acquisition still requires explicit owner approval for the manifest
  and an execution flag.

## Phase Tasks

- `F4D-ACQ-001`: Generate NBA team-season URL manifest and dry-run plan
  (`done`).
- `F4D-ACQ-LIVE-001`: Run owner-approved controlled NBA team-season cache
  acquisition (`done`; owner-approved 2000-2025 acquisition completed and
  reviewed).
- `F4D-ACQ-002`: Review acquisition report and cache coverage handoff
  (`done`).
- `F4D-001`: Cached HTML inventory (`done`).
- `F4D-002`: Full offline backfill command (`done`).
- `F4D-003`: Data quality validation checks (`done`).
- `F4D-004`: API-ready database readiness documentation (`done`).

## Phase 4D-A Scope

- NBA only.
- Team-season pages only.
- Basketball Reference season end years 2000 through 2025 inclusive.
- Exactly 775 unique NBA team-season URLs.
- Only URLs matching `/teams/{TEAM}/{YEAR}.html`.
- Explicit approved URL manifest before fetching.
- Live acquisition commands must include explicit start and end year arguments.
- The live command may run any inclusive subset inside the reviewed 2000-2025
  catalog.
- Existing `HtmlCache` path and `.html.gz` conventions.
- Cache-first acquisition that skips URLs already present.
- Fetch only missing cache entries during the approved live acquisition task.
- Write only `.html.gz` raw HTML through `HtmlCache`.
- Verify the deterministic manifest ID and exactly 775 entries before creating
  a live client, then filter by requested year range when a subset is requested.
- Do not overwrite existing cache hits.
- Store only non-empty HTML-shaped content; do not parse tables during
  acquisition.

## Phase 4D-A Disallowed Work

- Fetching HTML during planning, manifest generation, or dry-run work.
- Non-NBA pages.
- Player pages, boxscores, schedules, shot charts, or game logs.
- Database writes.
- Parser, loader, or backfill execution.
- API, frontend, generated metrics, OVR, ranking, similarity,
  recommendations, or ML work.
- Branch creation, commit, push, or PR without explicit owner approval.

## Acquisition Policy

- Default rate limit is 10 requests/minute.
- Configurable maximum for this phase is 12 requests/minute.
- Absolute hard cap is 20 requests/minute.
- Stop immediately on HTTP 429 and report partial results.
- Async is allowed only with strict bounded concurrency and a global rate
  limiter.
- Retry/backoff is allowed only for safe transient failures and must not bypass
  the global rate limiter.
- The command must be resumable and idempotent.
- Acquisition reports must include cache hits, fetched, skipped, failed, and
  rate-limited URLs.
- Acquisition report entries must include index, team, season end year, URL,
  cache path, status, and error details when applicable.
- Early-stop reports must include `stopped_reason` and `stopped_at_entry`.
- Acquisition reports must print as JSON to stdout and may also be written to
  an operator-provided output path.
- Sports Reference policy references:
  `https://www.sports-reference.com/bot-traffic.html` and
  `https://www.sports-reference.com/data_use.html`.

## URL Catalog Contract

Seasons 2000 through 2025 refer to Basketball Reference season end years.

The manifest generator must produce exactly 775 unique URLs from this NBA
team-season catalog:

- Stable teams for every season end year 2000-2025: `ATL`, `BOS`, `CHI`,
  `CLE`, `DAL`, `DEN`, `DET`, `GSW`, `HOU`, `IND`, `LAC`, `LAL`, `MIA`, `MIL`,
  `MIN`, `NYK`, `ORL`, `PHI`, `PHO`, `POR`, `SAC`, `SAS`, `TOR`, `UTA`, `WAS`.
- Grizzlies lineage: `VAN` for 2000-2001; `MEM` for 2002-2025.
- Hornets/Pelicans lineage: `CHH` for 2000-2002; `NOH` for 2003-2005 and
  2008-2013; `NOK` for 2006-2007; `NOP` for 2014-2025.
- Bobcats/Hornets expansion lineage: `CHA` for 2005-2014; `CHO` for
  2015-2025.
- Nets lineage: `NJN` for 2000-2012; `BRK` for 2013-2025.
- SuperSonics/Thunder lineage: `SEA` for 2000-2008; `OKC` for 2009-2025.

## Phase 4D-A Handoff Criteria

- Phase 4D-A tasks are implemented, reviewed, and marked `done`.
- The approved manifest and acquisition report cover the 775 expected NBA
  team-season URLs or clearly document remaining gaps.
- No disallowed page type was acquired.
- No database writes, parser/load/backfill execution, API/frontend/OVR/ranking/
  similarity/recommendations/ML work occurred.
- Phase 4D can then proceed through `F4D-001` cache inventory and `F4D-002`
  offline backfill before post-load data quality checks.

## Phase 4D Closure

Phase 4D is closed after the owner explicitly approved closing `F4D-002`,
`F4D-003`, and `F4D-004` together.

The closed Phase 4D baseline is:

```text
core.seasons                26
core.teams                  37
core.team_aliases           775
core.team_seasons           775
core.players                2551
core.player_seasons         12676
core.player_team_seasons    14344
```

The offline backfill report records 775 selected inventory entries, 775 loaded
entries, 129000 loaded rows, 0 failed entries, and 0 quarantined entries. The
readiness workflow is documented in
`docs/validation/OFFLINE_DATABASE_PREPARATION.md`.

No API, frontend, stats persistence, generated metrics, OVR, ranking,
similarity, recommendations, or ML implementation is included in Phase 4D.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`
