---
id: F8-012
title: Version snapshots of pages that still change
track: data
areas:
  - scraping
  - testing
  - documentation
priority: 91
depends_on: []
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/architecture/SYSTEM_DESIGN.md
  - docs/decisions/0004-rate-limited-scraping.md
  - src/nba_data/scraping/cache.py
  - src/nba_data/scraping/cache_writer.py
  - src/nba_data/scraping/cache_inventory.py
  - src/nba_data/config/settings.py
  - tests/unit/test_cache_inventory.py
validation:
  - uv run pytest tests/unit/test_snapshot_cache.py tests/unit/test_html_cache.py tests/unit/test_cache_inventory.py tests/unit/test_settings.py tests/unit/test_game_pilot_acquisition.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None. Offline cache code and tests only; no fetch.
---

# Goal

Let a page that still changes — the in-progress season's schedule and team
pages — be fetched again without ever overwriting what was cached before. Each
fetch becomes a new, timestamped snapshot; readers take the latest. The
never-overwrite guarantee of the cache stays whole, and the schedule's history
comes for free.

# Evidence and current state

- `HtmlCache.path_for_url` maps a URL to one file
  (`<slug>-<sha256[:16]>.html.gz`, `scraping/cache.py:125-143`), and
  `write_html_to_cache_safely` refuses an existing target
  (`scraping/cache_writer.py:37-57`). A first fetch of a partial schedule would
  therefore freeze it.
- `Settings.scraper_force_refresh` exists, but the writer still refuses to
  replace, and the older acquisition modules keep their own copies.
- `cache_inventory.py` walks every `*.html.gz` under `scraper_cache_dir`
  (`cache_inventory.py:99-108`) and matches team-season files by name; files
  added beside the archive could be misread by it.
- Every cache write already has a `CacheFetchMetadata` sidecar with an aware
  `fetched_at`.
- The pilot cached the October 2026-27 schedule page in the archive cache in
  2026-09; it is stale by design.

# Human decisions or resources

- [x] **Versioned snapshots, not a replace path** (decided 2026-10-18, F8-008):
      the cache keeps its never-overwrite contract, and every observation of a
      mutable page is kept.
- [x] **Separate root**: `Settings.scraper_snapshot_dir`, default
      `data/raw/snapshots`, outside `scraper_cache_dir`, so `cache_inventory`
      and every archive backfill never see a snapshot. Layout
      `<host dir>/<slug>-<sha256[:16]>/<fetched_at UTC, %Y%m%dT%H%M%S%fZ>.html.gz`
      plus its `.meta.json` sidecar, which is required for a snapshot.
- [x] **Mutable pages** are declared, not guessed: league schedule season and
      month pages and team-season pages (`/teams/<CODE>/<YEAR>.html`) whose
      season end year is `CURRENT_SEASON_END_YEAR` (2027, a constant changed
      by a card each season). Box scores are immutable: they are fetched only
      once a game has a score and go to the archive cache.
- [x] **Readers take the latest snapshot**; the archive-cache copy of an
      in-progress season page (the pilot's October page) is ignored by them.
- [x] **ADR 0022** records the decision. (ADR 0021 is reserved by F6-018.)

# Acceptance criteria

- `src/nba_data/scraping/snapshot_cache.py` (new): `SnapshotCache(root)` with
  `write(url, html, metadata) -> Path`, `latest(url) -> Snapshot | None`
  (body, metadata, path), and `history(url) -> tuple[Snapshot, ...]` oldest
  first; `is_mutable_page(url) -> bool`.
- `write` refuses: a URL that is not a mutable page; a missing or naive
  `fetched_at`; non-HTML content (`validate_html_for_cache`); an existing
  snapshot with the same timestamp. It publishes with the same
  refuse-existing primitive as `cache_writer.py` and verifies the body reads
  back byte-for-byte. A shared private helper may be factored out of
  `cache_writer.py` only if `write_html_to_cache_safely`'s behaviour and tests
  stay identical.
- `latest` orders by the `fetched_at` encoded in the file name and checks it
  equals the sidecar's; a mismatch or a body without a sidecar raises, never
  falls back.
- Tests: two writes of the same URL keep both and `latest` returns the second;
  `history` order; refusal of an immutable URL (box score, a 2026 team page);
  a crash between body and sidecar leaves nothing published; a snapshot never
  appears in `build_cached_html_inventory`; the archive cache is untouched.
- `.env.example` and `test_settings.py` gain `SCRAPER_SNAPSHOT_DIR`.
- `docs/decisions/0022-version-snapshots-of-pages-that-still-change.md` and the
  cache section of `SYSTEM_DESIGN.md` describe the two roots.

# Scope

`src/nba_data/scraping/snapshot_cache.py` (new), `cache_writer.py` (helper only),
`config/settings.py`, `.env.example`, `tests/unit/test_snapshot_cache.py` (new),
`tests/unit/test_settings.py`,
`docs/decisions/0022-…`, `docs/architecture/SYSTEM_DESIGN.md`.

# Out of scope

Any fetch or acquisition command (F8-013). Loaders (F8-014). Changing the
archive cache, its inventory, or the older acquisition modules.

# Impact

- New snapshot root; nothing writes to it until F8-013.

# Cross-track impact

- None.

# Implementation notes

- The writer's behaviour is pinned by `tests/unit/test_game_pilot_acquisition.py`;
  those tests must pass unchanged if a helper is factored out.
- Check `docs/decisions/` for the next free number first; if 0022 is taken, use
  the next one and update this card.

# Durable knowledge updates

- ADR 0022 and `docs/architecture/SYSTEM_DESIGN.md`.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command:
- Result:

## Manual happy path

1.
2.
3.

Expected result:

## Manual sad path

1.
2.
3.

Expected result:

## Known limitations

- None.
