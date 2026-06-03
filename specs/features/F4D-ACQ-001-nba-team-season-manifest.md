# F4D-ACQ-001 - NBA Team-Season Manifest

## Goal

Create the Phase 4D-A manifest generation and dry-run planning contract for NBA
team-season cache acquisition.

This task is planning-only for acquisition. It must not fetch HTML, write raw
HTML, contact Basketball Reference, write database rows, parse, load, backfill,
or implement API/frontend/generated metric work.

## Functional Requirements

- Generate an explicit approved URL manifest for Basketball Reference season
  end years 2000 through 2025 inclusive.
- Generate exactly 775 unique NBA team-season URLs.
- Allow only Basketball Reference team-season URLs matching
  `/teams/{TEAM}/{YEAR}.html`.
- Exclude non-NBA leagues, player pages, boxscores, schedules, shot charts, game
  logs, and all non-team-season pages.
- Use existing `HtmlCache` path conventions for dry-run reporting.
- Dry-run must report total URLs, cache hits, missing cache entries, skipped
  entries, unsupported entries, and estimated fetch count.
- Dry-run must not accept a network client.

## URL Catalog

Seasons 2000 through 2025 refer to Basketball Reference season end years.

The manifest generator must use this catalog:

- Stable teams for every season end year 2000-2025: `ATL`, `BOS`, `CHI`,
  `CLE`, `DAL`, `DEN`, `DET`, `GSW`, `HOU`, `IND`, `LAC`, `LAL`, `MIA`, `MIL`,
  `MIN`, `NYK`, `ORL`, `PHI`, `PHO`, `POR`, `SAC`, `SAS`, `TOR`, `UTA`, `WAS`.
- `VAN`: 2000-2001; `MEM`: 2002-2025.
- `CHH`: 2000-2002; `NOH`: 2003-2005 and 2008-2013; `NOK`: 2006-2007; `NOP`:
  2014-2025.
- `CHA`: 2005-2014; `CHO`: 2015-2025.
- `NJN`: 2000-2012; `BRK`: 2013-2025.
- `SEA`: 2000-2008; `OKC`: 2009-2025.

## Acceptance Criteria

- Feature spec exists at
  `specs/features/F4D-ACQ-001-nba-team-season-manifest.md`.
- The catalog covers Basketball Reference season end years 2000 through 2025
  inclusive.
- The manifest contains exactly 775 unique NBA team-season URLs.
- Every manifest URL matches `/teams/{TEAM}/{YEAR}.html`.
- Dry-run reports cache hits, missing cache entries, skipped entries,
  unsupported entries, and estimated fetch count without accepting a network
  client.
- No HTML is fetched and no `.html.gz` file is written.
- No database write, parser, loader, backfill, API, frontend, OVR, ranking,
  similarity, recommendations, or ML work is introduced.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference contact.
- Writing raw HTML.
- Database writes.
- Parser/load/backfill execution.
- API, frontend, generated metrics, OVR, ranking, similarity,
  recommendations, or ML work.
