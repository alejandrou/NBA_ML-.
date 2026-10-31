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
  a caught publication failure leaves no files; a killed writer leaves no
  complete snapshot, and its incomplete files are discoverable for manual
  recovery (ADR 0022); a snapshot never appears in
  `build_cached_html_inventory`; the archive cache is untouched.
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

## Automated validation

- Command: `uv run pytest tests/unit/test_snapshot_cache.py tests/unit/test_html_cache.py tests/unit/test_cache_inventory.py tests/unit/test_settings.py tests/unit/test_game_pilot_acquisition.py`
- Result: 138 passed under `-W error` (49 in `test_snapshot_cache.py`, 4 new in `test_settings.py`).
- Command: `uv run ruff check .` — Result: All checks passed.
- Command: `uv run mypy src/nba_data` — Result: no issues in 99 source files.
- Command: `uv run pytest` — Result: 1585 passed, 257 skipped, 7 warnings (none from the new tests).
- Command: `uv run python scripts/validate_tasks.py` — Result: passed.
- `cache_writer.py` is unchanged: `SnapshotCache` imports its `_publish` and
  `_remove_if_same_file` instead of factoring a helper out, so
  `write_html_to_cache_safely` and `test_game_pilot_acquisition.py` are untouched.

### Review round 1 (2026-10-31)

Five findings, all fixed, each with a regression test in `test_snapshot_cache.py`:

1. **Path escape through a link** — `directory_for_url` now checks the page
   directory itself after resolving links, and `write`/readers check every file
   they touch. `test_write_refuses_a_link_that_leaves_the_root` (junction at the
   page and at the host directory) and `test_reads_refuse_a_link_that_leaves_the_root`.
2. **`latest` loaded every body** — names and sidecars are still all checked;
   only the newest body is read. `test_latest_reads_only_the_newest_body`
   (corrupt oldest body: `latest` succeeds with one read, `history` raises) and
   `test_latest_still_checks_every_older_sidecar`.
3. **Crash test overstated** — `test_a_killed_writer_leaves_an_incomplete_write_that_recovery_clears`
   kills a subprocess with `os._exit` between the publishes. New read-only
   `incomplete_writes(url)` lists the leftovers; ADR 0022 records the manual
   recovery (no writer running → delete the listed files).
4. **Raw exception types** — impossible stamps and unreadable bodies (truncated,
   not gzip, not UTF-8) raise `SnapshotCacheError` with the cause chained; a
   link at the host directory raises `SnapshotCacheError` instead of `ValueError`.
5. **Writable but unreadable metadata** — `write` round-trips the sidecar
   through the reader's own parser before writing anything.
   `test_write_refuses_metadata_its_reader_would_reject` (`"200"`, `True`, `123`)
   and `test_write_refuses_a_fetch_time_that_is_not_a_datetime`.

### Review round 2 (2026-10-31)

- Rechecked all five findings against the implementation and regression tests;
  no major remaining defects or improvements needed before closure.
- Re-ran the focused validation command with `-W error`: 138 passed.
- Re-ran `uv run pytest`: 1585 passed, 257 skipped, 7 dependency deprecation
  warnings. The PostgreSQL integration lane remained skipped without opt-in.
- Re-ran `uv run ruff check .` and `uv run mypy src/nba_data`: both passed.
- After moving to done, both `scripts/validate_tasks.py` and
  `scripts/validate_tasks.py --all-worktrees` passed.
- Clarified the crash acceptance criterion to distinguish caught-error rollback
  from abrupt process termination and the documented manual recovery.
- The user authorized moving the task to done, committing, and pushing after
  this review. No cross-track handoff or parked-card bookkeeping is needed.

## Manual happy path

1. `uv run python -c "from datetime import UTC, datetime; from nba_data.scraping.cache import CacheFetchMetadata as M; from nba_data.scraping.snapshot_cache import SnapshotCache; c = SnapshotCache('C:/tmp/snap'); u = 'https://www.basketball-reference.com/leagues/NBA_2027_games-october.html'; html = '<!DOCTYPE html><html>{}</html>'; [c.write(u, html.format(d), M(datetime(2026, 10, d, tzinfo=UTC), 200, u)) for d in (20, 21)]; print([s.path.name for s in c.history(u)], c.latest(u).body)"`
2. Look under `C:/tmp/snap/basketball-reference/leagues-nba_2027_games-october.html-<digest>/`.
3. Delete `C:/tmp/snap` afterwards.

Expected result: two `.html.gz` files, each with a `.meta.json` sidecar;
history prints `20261020T000000000000Z.html.gz` then `20261021…`; latest body
ends in `21</html>`.

## Manual sad path

1. Same setup, writing `https://www.basketball-reference.com/boxscores/202610210BOS.html`
   or `.../teams/BOS/2026.html` → `CacheWriteError: Refusing to snapshot a page that is not mutable`.
2. Repeat step 1 of the happy path → `CacheWriteError: Refusing to overwrite existing snapshot file`.
3. Delete one `.meta.json` sidecar, then call `c.latest(u)` → `SnapshotCacheError: Snapshot has no metadata sidecar`.
4. `uv run python -c "from nba_data.config.settings import Settings; Settings(scraper_snapshot_dir='data/raw/html/snap')"`
   → validation error naming `SCRAPER_SNAPSHOT_DIR`.

Expected result: every refusal leaves no new file behind.

## Known limitations

- The mutable rule applies `CURRENT_SEASON_END_YEAR` to the schedule pages as
  well as the team pages (the card's sentence could be read either way); a
  2026 schedule page is immutable and goes to the archive cache.
- `/teams/<CODE>/2027_games.html` is not mutable: ADR 0020 does not use team
  schedule pages.
- A process killed after the sidecar publishes but before the body leaves an
  orphan sidecar and a temp body; readers ignore them, and the sidecar blocks a
  rewrite with that exact timestamp. Recovery is manual by design
  (`incomplete_writes`, ADR 0022). Nothing prunes old snapshots.
- The archive writer (`write_html_to_cache_safely`) has the same
  unvalidated-metadata gap as finding 5; it is out of this card's scope and
  unchanged.
- Link checks resolve paths before use; a link swapped in between the check
  and the write is not defended against (same as the archive cache).
- Settings now reject an overlapping `SCRAPER_SNAPSHOT_DIR` — a guard beyond the
  card's text that enforces its "separate root" decision.
