# F4C-001 - Offline Cached HTML Processor

## Goal

Implement the first Phase 4C runtime boundary for already-cached Basketball
Reference team-season HTML.

The processor reads existing `.html.gz` cache files, parses the HTML, normalizes
the parsed rows, and validates normalized output. It returns validated
normalized rows and actionable failures only. It does not load the database.

Required order:

```text
.html.gz -> parse_team_season_page -> normalize_team_season_page -> validate_normalized_team_season_rows
```

## Functional Requirements

- Inputs may reference a Basketball Reference team-season URL resolved through
  `HtmlCache.path_for_url(...)`, or an explicit `.html.gz` path under the
  configured cache root.
- Explicit path inputs must include team abbreviation and season end year
  metadata because no network lookup is allowed.
- Cache misses are hard failures. The processor must not call `HtmlCache.set`,
  `BasketballReferenceClient`, `requests`, `httpx`, or any generic network
  client.
- URL inputs must be explicit Basketball Reference team-season pages matching
  `/teams/{TEAM}/{YEAR}.html`.
- Explicit paths must resolve under the configured cache root, must end in
  `.html.gz`, and must be read-only inputs.
- Each cached team-season page is read once per processing run and then feeds
  the existing parser, normalizer, and validator.
- Successful output is validated normalized rows plus source context.
- Failed output includes actionable source context and validation or read
  errors. A failed input must not block reporting for other inputs.

## Technical Requirements

- Keep parsing, normalization, and validation separate:
  `parse_team_season_page(...)`, then `normalize_team_season_page(...)`, then
  `validate_normalized_team_season_rows(...)`.
- Default execution is sequential with `max_workers=1`.
- If `max_workers > 1` is implemented, it must use bounded local-only work over
  already-cached files and preserve input order in the final report.
- Do not introduce database sessions, loader calls, migrations, raw HTML
  deletion, cache refresh, API, frontend, generated metrics, OVR, ranking,
  similarity, or ML behavior.
- A CLI command is not required for `F4C-001`; operator reporting and
  quarantine workflow remain later Phase 4C work unless separately approved.

## Acceptance Criteria

- Processor reads only existing `.html.gz` cache entries or explicit paths
  under the cache root.
- Cache misses fail and never refresh the cache.
- No network client is accepted or imported by the processor.
- Processing order is `.html.gz -> parse -> normalize -> validate`.
- Default execution is sequential with `max_workers=1`.
- Any concurrency is bounded and limited to local cached HTML work.
- Processor output is validated normalized rows and actionable errors, not
  database writes.
- Tests use local fixtures or temporary cache files only.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference contact.
- Refreshing cache misses.
- Database loading or SQLAlchemy migrations.
- Full historical loading.
- API, frontend, generated metrics, OVR, ranking, similarity, or ML work.
- Deleting raw HTML, database records, volumes, Peewee code, or legacy code.
