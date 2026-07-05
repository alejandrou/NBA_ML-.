# F4E-010 - Player-Page Cache Acquisition

## Goal

Acquire missing Basketball Reference player pages into `HtmlCache` from the
existing `core.players.basketball_reference_player_id` catalog so the Phase 4E
cache-only player-page backfills can process real cached HTML.

This task is the only Phase 4E task allowed to contact Basketball Reference
after explicit owner approval and explicit manifest execution confirmation.

## Functional Requirements

- Build a deterministic player-page manifest from
  `core.players.basketball_reference_player_id`.
- Allow optional filtering by `core.seasons.season_year` through
  `core.player_seasons`.
- Build URLs only as
  `https://www.basketball-reference.com/players/{first_letter}/{player_id}.html`.
- Add `acquisition dry-run-player-pages`.
- Add `acquisition acquire-player-pages`.
- Support `--limit`, `--player`, `--start-year`, `--end-year`, and `--output`.
- Refuse live acquisition without both `--owner-approved` and
  `--execute-approved-manifest`.
- Use `BasketballReferenceClient` and `HtmlCache` only.
- Keep acquisition cache-first, sequential, and rate-limited.
- Use the project default conservative live rate of at most 10 requests/minute.
- Never exceed the global hard cap of 20 requests/minute.
- Do not overwrite existing cache files.
- Do not write database rows.
- Validate fetched content is non-empty and HTML-shaped before storing it.
- Stop immediately on HTTP 429 or any failed fetch and emit a partial JSON
  report.
- Produce JSON reports with `total_players`, `cache_hits`, `fetched`,
  `failures`, `live_request_count`, and per-entry results.
- Allow resumable reruns: existing cache hits must stay cache hits and skipped
  pages must not trigger a live request.

## Acceptance Criteria

- Feature spec exists at
  `specs/features/F4E-010-player-page-cache-acquisition.md`.
- The manifest is deterministic for the same DB state and filters.
- The manifest can be filtered by exact `basketball_reference_player_id`.
- The manifest can be filtered by inclusive season-year bounds through
  `core.player_seasons`.
- Player-page URLs match the official `/players/{initial}/{player_id}.html`
  pattern.
- The dry-run command reports cache hits and missing cache entries without
  creating a live client.
- The live command refuses to run without both approval flags.
- Live acquisition validates settings and manifest inputs before creating a live
  client.
- Existing cache hits never trigger a live request or overwrite a cache file.
- Cache misses fetch through `BasketballReferenceClient`, then write `.html.gz`
  files under `HtmlCache`.
- No database rows are inserted, updated, or deleted during manifest planning
  or acquisition.
- HTTP 429 stops immediately and returns a partial report.
- Other fetch or cache-write failures stop immediately and return a partial
  report.
- The JSON report is printed to stdout and, when `--output` is provided,
  written to that path as the same JSON.
- Player-page regular-season and postseason loaders remain cache-only.
- No Phase 5 API work starts.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `uv run alembic check`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Running live acquisition without explicit owner approval.
- Refreshing or overwriting existing player-page cache files.
- Writing parser, loader, or stats rows during acquisition.
- Modifying the player-page regular-season or postseason loaders except for
  narrow integration wiring.
- Team-season acquisition changes beyond shared CLI/reporting conventions.
- API, frontend, generated metrics, OVR, ranking, similarity,
  recommendations, or ML work.
