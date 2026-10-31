# ADR 0022 - Version Snapshots of Pages That Still Change

## Status

Accepted, 2026-10-31, by F8-012. Decided 2026-10-18 while planning F8-008.

## Context

The archive cache (ADR 0003) maps one URL to one `.html.gz` file, and the
gated writer `write_html_to_cache_safely` refuses an existing target. That is
right for a finished season: a page is fetched once and becomes the raw source
of truth. It is wrong for a season in progress. The league schedule and the
team-season pages of the current season change every day, so the first fetch
would freeze them; the pilot's October 2026-27 schedule page, cached in
2026-09, is already stale.

Two ways out were considered: give the archive writer a replace path, or keep
every observation of a mutable page.

## Decision

Pages that still change are kept as **versioned snapshots** in a second root,
and the archive cache keeps its never-overwrite contract unchanged.

- **Root.** `Settings.scraper_snapshot_dir` (`SCRAPER_SNAPSHOT_DIR`), default
  `data/raw/snapshots`, outside `scraper_cache_dir`. Settings refuse a snapshot
  root that equals, contains, or sits inside the cache root, because
  `cache_inventory` and every archive backfill walk all of `*.html.gz` there.
- **Layout.**
  `<host dir>/<slug>-<sha256[:16]>/<fetched_at UTC, %Y%m%dT%H%M%S%fZ>.html.gz`
  plus its `.meta.json` sidecar. Host directory, slug and digest are the
  archive cache's own, so a page has the same name in both roots.
- **Mutable pages are declared.** `is_mutable_page` accepts only the league
  schedule season and month pages (`/leagues/NBA_<year>_games[-<month>].html`)
  and the team-season pages (`/teams/<CODE>/<year>.html`) whose year is
  `CURRENT_SEASON_END_YEAR` (2027). A card changes that constant each season.
  Box scores are immutable: they are fetched only once a game has a score and go
  to the archive cache.
- **Writes never replace.** `SnapshotCache.write` refuses a page that is not
  mutable, missing or naive `fetched_at`, metadata its own reader would reject
  (checked by a serialize-and-parse round trip before anything is written),
  non-HTML content, and an existing snapshot with the same timestamp. It
  publishes with the archive writer's own refuse-existing primitive, sidecar
  first, so a body is never visible without the sidecar that dates it; a failed
  body publish removes that sidecar again.
- **Paths stay inside the root.** The page directory and every file written or
  read in it are resolved — links and Windows junctions included — and refused
  when they land outside the snapshot root.
- **Readers take the latest.** `latest` and `history` order snapshots by the
  timestamp in the file name and require it to equal the sidecar's
  `fetched_at`. Both check every name and sidecar: a body without a sidecar, an
  unreadable sidecar, a mismatch, or a name that is not a valid stamp raises;
  there is no fallback. `latest` then reads only the newest body, so an older
  unreadable body does not block it; `history` reads them all. Unreadable bodies
  and impossible stamps raise `SnapshotCacheError` with the underlying error as
  its cause. The archive copy of a mutable page is ignored by snapshot readers.
- **A killed writer leaves an incomplete write, recovered by hand.** A process
  killed between the two publishes leaves a sidecar without a body and a temp
  body. On POSIX, the sidecar's temporary hard-link name also remains.
  These files are not snapshots and readers ignore them; the orphan sidecar only
  refuses a rewrite with its exact timestamp, and a real refetch has a new one.
  `SnapshotCache.incomplete_writes(url)` lists these files without touching
  them. Recovery: with no writer running for that page, delete the listed files.
  Nothing deletes them automatically, because a live writer's just-published
  sidecar looks the same.

## Consequences

- The schedule's history comes for free: every refresh is kept, so a past
  state of the season can be replayed.
- Disk grows with each refresh; nothing prunes old snapshots.
- Nothing writes snapshots until the current-season refresh (F8-013); loaders
  that read them arrive with F8-014.
- Rolling the season over is a code change to `CURRENT_SEASON_END_YEAR`. Once
  a season ends, its final pages belong in the archive cache.

## Alternatives Considered

- **A replace path in the archive writer** (`scraper_force_refresh`): rejected.
  It loses every earlier observation and weakens the never-overwrite guarantee
  that the archive's reproducibility rests on.
- **Snapshots inside the archive root**: rejected. The inventory and backfills
  would read them as archived pages.
- **Guessing mutability from fetch age or page content**: rejected. A declared
  rule is testable and cannot drift silently.
