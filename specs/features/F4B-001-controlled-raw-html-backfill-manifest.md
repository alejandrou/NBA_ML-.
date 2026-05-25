# F4B-001 - Controlled Raw HTML Backfill Manifest

## Goal

Design the controlled raw HTML backfill manifest and approval workflow before
any runtime backfill runner, live request, parser/load step, or database write
is implemented.

The target acquisition path is:

```text
approved manifest -> BasketballReferenceClient -> HtmlCache -> .html.gz
```

This task is documentation-only. It defines the contract that later Phase 4B
tasks must validate and execute, but it does not create a live manifest, run
scraping, contact Basketball Reference, write database rows, apply migrations,
or implement a runner.

## Manifest Contract

The default manifest format is JSON so the project can validate it later
without adding dependencies. A manifest is a reviewed acquisition plan, not a
general crawler configuration.

Required manifest intent:

- Every entry lists one explicit Basketball Reference URL.
- Every entry declares a supported `page_type`.
- The first supported pilot page type is `team_season` for URLs matching
  `/teams/{TEAM}/{YEAR}.html`.
- The manifest records enough approval metadata for a future runner to refuse
  unapproved live acquisition.
- The manifest records acquisition limits: sequential execution, cache-first
  behavior, default 10 requests/minute, and absolute max 20 requests/minute.
- The manifest states that raw HTML may be written only through `HtmlCache` as
  `.html.gz`.

Illustrative shape:

```json
{
  "manifest_id": "pilot-team-season-YYYYMMDD",
  "status": "draft",
  "approved_by_owner": false,
  "approved_at": null,
  "scope": {
    "page_type": "team_season",
    "max_urls": 5
  },
  "acquisition_policy": {
    "cache_first": true,
    "sequential": true,
    "requests_per_minute": 10,
    "max_requests_per_minute": 20,
    "write_target": "HtmlCache .html.gz"
  },
  "entries": [
    {
      "page_type": "team_season",
      "url": "https://www.basketball-reference.com/teams/BOS/2024.html",
      "team": "BOS",
      "season_end_year": 2024
    }
  ]
}
```

The example is not an approved live manifest. Any real manifest must go
through the approval protocol below before a future runner may make a live
request.

## Pilot Scope

- The default first pilot is at most five `team_season` URLs.
- `team_season` URLs must be explicit Basketball Reference team-season pages:
  `/teams/{TEAM}/{YEAR}.html`.
- Cache hits make no live requests.
- Cache misses may later make at most one live request each through
  `BasketballReferenceClient`, after exact owner approval.
- Player-specific Basketball Reference pages are out of scope for the initial
  pilot. They require a later explicit task and manifest approval.
- Full historical scraping is out of scope. A manifest must not imply broad
  season/team expansion beyond the approved entries.

## Approval Protocol

- A draft manifest is prepared and reviewed before any live acquisition.
- `F4B-002` will add offline dry-run validation for the manifest without
  contacting Basketball Reference.
- The owner must explicitly approve the exact manifest before any live request.
- Approval applies only to the exact URLs, page types, limits, and metadata in
  that manifest.
- Any URL, scope, page type, rate limit, or acquisition policy change requires
  fresh owner approval.
- A future runner must refuse live acquisition unless manifest metadata records
  explicit owner approval.
- The future `F4B-LIVE-001` pilot must report cache hits, cache misses,
  fetched pages, failures, and skipped entries without writing DB rows.

## Guardrails

- No live scraping or Basketball Reference contact is performed by this task.
- No runtime backfill runner is implemented by this task.
- No DB writes, migrations, loader execution, offline parse/load processing,
  API/frontend work, OVR, rankings, similarity, ML, or historical full scrape
  are introduced.
- Live acquisition, when later approved, remains sequential, cache-first, and
  rate-limited through `BasketballReferenceClient`.
- Raw HTML remains separate from parsed rows, normalized rows, generated
  metrics, and database load outputs.

## Acceptance Criteria

- Feature spec exists at
  `specs/features/F4B-001-controlled-raw-html-backfill-manifest.md`.
- The design documents
  `approved manifest -> BasketballReferenceClient -> HtmlCache -> .html.gz`.
- The manifest design supports explicit Basketball Reference URLs and page
  types.
- The initial pilot scope defaults to at most five `team_season` URLs matching
  `/teams/{TEAM}/{YEAR}.html`.
- Live acquisition is documented as sequential, cache-first, 10 requests/minute
  by default, and never above 20 requests/minute.
- The owner must approve the exact manifest before any live request.
- Player-specific pages are excluded from the initial pilot unless a later
  explicit task and manifest approve them.
- The design performs no DB writes, migrations, parser/load runtime work,
  API/frontend/OVR work, or historical full scrape.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`
