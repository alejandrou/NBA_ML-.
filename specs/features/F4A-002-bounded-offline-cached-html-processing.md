# F4A-002 - Bounded Offline Cached HTML Processing

## Goal

Design the future offline processing path for already-cached Basketball
Reference team-season HTML without implementing a runtime processor yet.

The target flow is:

```text
cached .html.gz
-> parse_team_season_page
-> normalize_team_season_page
-> validate_normalized_team_season_rows
-> future Phase 4 idempotent loader boundary
```

This design exists so controlled raw HTML backfill can later separate live
acquisition from local parsing, normalization, validation, and loading.

## Functional Requirements

- The offline processor reads only already-cached `.html.gz` files through
  `HtmlCache` or explicit cache file paths under the configured cache root.
- Cache misses are hard failures. The offline processor must not refresh cache
  entries or attempt live acquisition.
- The processor accepts no `BasketballReferenceClient`, `httpx`, `requests`,
  or generic network client.
- Parsing uses `parse_team_season_page(html)` with an HTML string.
- Normalization uses `normalize_team_season_page(...)` after parsing and keeps
  normalization separate from parser behavior.
- Validation uses `validate_normalized_team_season_rows(...)` or
  `assert_valid_normalized_team_season_rows(...)` before any future load.
- Processor output should be validated normalized rows and actionable
  validation errors, not database writes.
- Future DB writes are delegated to Phase 4 idempotent loaders and must occur
  only after validation passes.

## Technical Requirements

- Default execution is sequential with `max_workers=1`.
- Thread workers may be used only for bounded local gzip reads and
  parse/normalize/validate batches where I/O wait dominates.
- Process workers may be used only for CPU-heavy offline parsing or validation
  after profiling shows local CPU is the bottleneck.
- Async may be used only as local orchestration over already-cached inputs. It
  must never schedule live Basketball Reference acquisition.
- Worker count must be configurable and bounded; unbounded fan-out is not
  allowed.
- Each cached team-season page should be read once per processing run and feed
  all supported table parsing for that page.
- Parser, normalizer, and validator code must remain pure or side-effect-light:
  no network calls, DB writes, migrations, cache writes, or generated metrics.
- `TOT` remains an aggregate row context, not a real team.
- `player_name` remains descriptive only and must not be treated as a stable
  key.

## Acceptance Criteria

- Feature spec exists at
  `specs/features/F4A-002-bounded-offline-cached-html-processing.md`.
- The design reads only `.html.gz` files from `HtmlCache` or explicit cache
  paths under the cache root.
- No network client is accepted by the offline processor.
- Cache misses fail instead of making live requests or refreshing the cache.
- Concurrency is bounded and configurable.
- The design states when to use sequential, thread, process, or async
  execution.
- Parser, normalizer, and validator remain pure or side-effect-light.
- DB writes are delegated to later Phase 4 idempotent loaders.
- Future tests use local fixtures or temporary `.html.gz` cache files only.
- No live scraping, controlled raw HTML backfill, DB schema changes, DB writes,
  API/frontend/OVR work, or legacy/Peewee deletion is introduced.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`
