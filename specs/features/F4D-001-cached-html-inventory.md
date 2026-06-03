# F4D-001 - Cached HTML Inventory

## Goal

Build a repeatable inventory of all cached `.html.gz` files currently available
under the configured cache root.

The inventory is a discovery and reporting boundary only. It does not write to
the database, run live scraping, refresh cache misses, or contact Basketball
Reference.

## Functional Requirements

- Discover cached `.html.gz` files under the configured cache root.
- Identify the source URL or source path where possible.
- Extract or infer team abbreviation and season year where possible.
- Distinguish valid Basketball Reference team-season page candidates from
  unsupported paths, duplicate candidates, missing metadata, invalid files, and
  unreadable files.
- Report total discovered files, valid candidates, invalid or unreadable files,
  duplicate candidates, missing metadata, and unsupported paths.
- Return an inventory result structure suitable for later Phase 4D backfill
  work.
- Optionally write a JSON report if that matches the existing reporting
  patterns chosen during implementation.

## Technical Requirements

- Use configured cache-root paths and keep all filesystem reads inside that
  boundary.
- Do not import or accept `BasketballReferenceClient`, `requests`, `httpx`, or
  a generic network client.
- Do not call `HtmlCache.set(...)` or any cache refresh/acquisition path.
- Do not create SQLAlchemy sessions, call loaders, run migrations, or write
  database rows.
- Tests must use local temporary cache fixtures only.

## Acceptance Criteria

- Feature spec exists at `specs/features/F4D-001-cached-html-inventory.md`.
- Inventory discovers existing `.html.gz` files under the configured cache root.
- Inventory identifies source URL or path where possible.
- Inventory extracts or infers team abbreviation and season year where
  possible.
- Inventory distinguishes valid team-season candidates from unsupported,
  duplicate, missing-metadata, invalid, and unreadable files.
- Inventory reports total discovered files, valid candidates, invalid or
  unreadable files, duplicate candidates, missing metadata, and unsupported
  paths.
- Inventory does not write to the database.
- Inventory does not scrape, refresh cache misses, or contact Basketball
  Reference.
- Tests use local temporary fixtures only.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference contact.
- Cache refresh or acquisition.
- Database writes, loaders, or migrations.
- Deleting raw HTML, database records, local databases, or PostgreSQL volumes.
- API, frontend, generated metrics, OVR, ranking, similarity,
  recommendations, or ML work.
