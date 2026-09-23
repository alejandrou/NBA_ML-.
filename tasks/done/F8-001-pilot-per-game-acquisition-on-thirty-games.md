---
id: F8-001
title: Pilot per-game acquisition on thirty games
track: data
areas:
  - scraping
  - data-quality
  - testing
  - documentation
priority: 100
depends_on: []
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/decisions/0003-cache-raw-html.md
  - docs/decisions/0004-rate-limited-scraping.md
  - docs/decisions/0016-live-vs-offline-validation.md
  - docs/validation/PLAYER_PAGE_CACHE_ACQUISITION.md
  - docs/domain/BUSINESS_RULES.md
  - src/nba_data/scraping/client.py
  - src/nba_data/scraping/cache.py
  - src/nba_data/scraping/player_page_acquisition.py
  - src/nba_data/scraping/nba_team_season_acquisition.py
  - src/nba_data/scraping/nba_team_season_manifest.py
  - src/nba_data/scraping/backfill_manifest.py
  - src/nba_data/scraping/cache_inventory.py
  - src/nba_data/scraping/player_page_cache.py
  - src/nba_data/scraping/parsers/team_season.py
  - src/nba_data/cli/main.py
  - tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json
validation:
  - uv run pytest tests/unit/test_game_pilot_manifest.py tests/unit/test_game_pilot_acquisition.py tests/unit/test_league_schedule_parser.py tests/unit/test_box_score_parser.py tests/unit/test_play_by_play_parser.py tests/unit/test_game_pilot_validation.py tests/unit/test_rate_limited_client.py
  - uv run pytest tests/unit/test_nba_team_season_acquisition.py tests/unit/test_player_page_acquisition.py tests/unit/test_backfill_manifest.py tests/unit/test_cache_inventory.py tests/unit/test_stats_coverage_artifact.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Live acquisition from Basketball Reference of the two pilot manifests (league schedule pages first, then box score and play-by-play pages of the thirty selected games), each through the gated acquire-game-pilot command. Needs the owner's direct, current instruction; the card never authorizes it.
---

# Goal

Stage 1 of `docs/ml/PREDICTOR_PLAN.md`: prove, on thirty games, that per-game
data (schedule, final result, team and player box score, play-by-play) can be
acquired, cached, parsed offline, and reconciled — before any schema is written
or any large acquisition is planned. The deliverable is a measured go/no-go
report, not a dataset.

# Evidence and current state

- There is no per-game data anywhere: `alembic/versions/` ends at
  `0008_drop_raw_schema`, and no model in `src/nba_data/db/models/` has a game
  grain. The `stats.*_pbp` tables are season summaries.
- Every acquisition path is bound to Basketball Reference and gated the same
  way (evidence for locating the gate, not its boundary):
  `cli/main.py` `acquire-nba-team-seasons` and `acquire-player-pages` refuse
  without `--owner-approved` and `--execute-approved-manifest` before building
  a client; `scraping/client.py` `BasketballReferenceClient` owns the cache
  hand-off, the 6-second floor, the 20/min cap, and stop-on-429
  (`max_429_retries=0` in every acquire command); each acquisition module
  writes through an atomic, never-overwrite cache writer with provenance
  sidecars (ADR 0003, F4E-028).
- Basketball Reference identifiers are what `core` is keyed on:
  `core.players.basketball_reference_player_id` and Basketball Reference team
  codes in `core.teams`/`core.team_seasons`. The local cache mirrors them — 2,551
  player pages and the 775 reviewed team-season pages
  (`nba_team_season_manifest.py`), matching the 2,551 players and 775
  team-seasons the plan counted on 2026-09-12.
- Cache discovery is filename-based and tolerates other page kinds under
  `data/raw/html/basketball-reference/`: `cache_inventory.py` classifies a
  non-`teams-*` file as `unsupported_path` (skipped by every backfill), and the
  stats-coverage fingerprint hashes only `players-*` files and valid team-season
  entries. Box score (`boxscores-*`) and league schedule (`leagues-*`) files
  change neither. A `/teams/<CODE>/<YEAR>_games.html` page would: its filename
  matches the loose team-season pattern and would surface as a
  `missing_metadata` coverage issue — so the pilot never requests team schedule
  pages.
- The team-season pages carry a play-by-play summary table (`pbp_stats`) from
  1999–2000 onward (`BOS/2000` has 15 rows), so game play-by-play may exist for
  the whole archived range; the pilot measures it instead of assuming it.
- `SCRAPER_USER_AGENT` still holds the `.env.example` placeholder. The player-page
  procedure requires a real contact; the public repository URL is one that does
  not disclose a personal address.

# Human decisions or resources

- [x] **Provider: Basketball Reference** — box score
      (`/boxscores/<id>.html`), play-by-play (`/boxscores/pbp/<id>.html`), and
      league schedule (`/leagues/NBA_<year>_games[-<month>].html`) pages. Its
      player and team ids are the ones `core` is keyed on, so identity
      resolution needs no cross-provider mapping (the plan forbids resolving
      one by name); it reuses the one client, cache, and gate unchanged; and it
      stays within the access the owner already accepted for 3,326 pages, where
      NBA.com would need the owner to accept its terms personally. With the same
      6-second floor NBA.com offers no per-game speed advantage. NBA.com stays a
      candidate only for Stage 4 play-by-play (`pbpstats`), behind its own
      pilot and the owner's terms decision. Recorded in ADR 0019.
- [x] **Client:** the existing `BasketballReferenceClient` over `httpx`. No
      dependency change, so no `shared` card.
- [x] **Limits:** no second provider, so the Basketball Reference limits apply
      unchanged: 6-second floor, 10/min default, 20/min cap, honor
      `Retry-After`, stop on the first 429. The pilot command refuses settings
      above 10/min, like `acquire-player-pages`.
- [x] **Pilot content:** schedule, box score, and play-by-play for all thirty
      games.
- [x] **Game selection:** thirty games over nine seasons — 2000 (1), 2001 (2),
      2010 (2), 2015 (3), 2020 (4), 2021 (3), 2024 (5), 2025 (4), 2026 (6) —
      drawn from the acquired schedule pages: each season's opening game, its
      longest overtime game in the fetched months, and its edge cases (the
      2019–20 suspension and bubble, empty arenas in 2020–21, NBA Cup knockout
      and final games, games played abroad), with remaining slots filled by the
      mid-month game of a fetched month. Upcoming 2026–27 games are covered by
      schedule parsing only. The list and each game's reason live in the
      approved manifest. The owner delegated this approval on 2026-09-23 ("act
      as owner, take your best assumptions, do not ask").

# Acceptance criteria

1. **Manifest contract** (`scraping/game_pilot_manifest.py`): a pilot manifest
   loads only when `status` is `approved`, `approved_by_owner` is `true`, and
   `approved_at` is a timezone-aware ISO timestamp; its policy is cache-first,
   sequential, stop-on-first-failure, at most 10 requests/minute with a cap of
   at most 20, writing `HtmlCache .html.gz`; it holds 1–100 entries, none
   duplicated, each an explicit `https://www.basketball-reference.com` URL of
   exactly one of three page types — `league_schedule`, `box_score`,
   `play_by_play` — matching that type's strict path, with no query or
   fragment; a game entry's `game_id` equals the URL's, its date is a real date
   inside the season's window, and its home code is not a synthetic team code.
   Every rejection has a test.
2. **Gate:** `nba-data acquisition acquire-game-pilot MANIFEST --owner-approved
   --execute-approved-manifest` prints
   `Refusing acquisition without --owner-approved and --execute-approved-manifest`
   and exits 1 before reading the manifest or creating a client when either flag
   is missing; an invalid manifest or settings above 10/min fail before a client
   exists. Tests prove all three. The existing acquire commands, their guards,
   and their tests are unchanged.
3. **Acquisition** (`scraping/game_pilot_acquisition.py`): cache-first,
   sequential, never overwrites a body or sidecar (not even one another process
   publishes mid-write), refuses empty or non-HTML
   content, writes provenance sidecars, and stops at the first 429 (client built
   with `max_429_retries=0`) or failure with a partial JSON report. Per entry it
   records status, HTTP requests made (including in-client retries), decoded and
   compressed bytes, and wall time; the report totals them.
   `nba-data acquisition dry-run-game-pilot MANIFEST` plans the same manifest
   without creating a client.
4. **Parsers** (`scraping/parsers/league_schedule.py`, `box_score.py`,
   `play_by_play.py`): pure functions from HTML to typed results, no network or
   database, tested against trimmed real pages in `tests/fixtures/html/`. The box
   score keeps "did not play" and inactive players distinct from played lines
   with zeros, and classifies the game from its heading: regular season,
   play-in, playoffs, or NBA Cup final. The schedule keeps unplayed games and
   play-in rows distinct. *Amended after the live run:* the draft asked the
   schedule to tell regular season from playoffs, but the real pages carry no
   such marker, so that duty moved to the box score heading.
5. **Offline validation** (`nba-data validate game-pilot`): from the manifest
   and the cache only, reports per game — team codes against the reviewed
   team-season catalog and player ids against the cached player pages; final
   score agreement across schedule, scorebox, team totals, line score, and
   play-by-play; per-period points; player sums against team totals; minutes;
   participation classes — and exits non-zero on any unexplained mismatch.
   *Amended after review:* it also exits non-zero when the manifests name no
   game or leave out a game's box score or linked play-by-play, reads a blank
   value as missing and never as zero, and reports a malformed page as failed
   checks instead of raising.
6. **Pilot report** `docs/validation/PER_GAME_ACQUISITION_PILOT.md`: the per-game
   results, measured requests, bytes, and wall time, the `pbpstats`
   compatibility verdict, every gap found, a go/no-go per data type, and the
   recommended pages and cost for Stage 2.
7. **Decision record:** ADR 0019 records the provider decision;
   `docs/ml/PREDICTOR_PLAN.md` names the chosen provider and pages; F8-002's
   first open decision is resolved from the pilot's findings.
8. No database writes, no schema change, no migration.

# Scope

`src/nba_data/scraping/` (pilot manifest, acquisition, a behaviour-neutral
request counter in `client.py`, the three parsers), `src/nba_data/validation/`
(pilot validation), `src/nba_data/cli/main.py` (three new commands),
`tasks/manifests/` (the two pilot manifests), `tests/unit/`,
`tests/fixtures/html/`, `docs/validation/`, `docs/decisions/`,
`docs/ml/PREDICTOR_PLAN.md`, and F8-002's planning card.

# Out of scope

Tables, migrations, loaders, and any database write (`F8-002`). Acquisition
beyond the two pilot manifests. NBA.com, `nba_api`, and `pbpstats` as
dependencies. Model training. Changing the Basketball Reference limits, the
existing acquire commands, or their guards.

# Impact

- **Scraping:** three new CLI commands and a pilot manifest format; box score,
  play-by-play, and league schedule pages join the Basketball Reference cache.
- **Client:** a read-only request counter; request behaviour unchanged.
- **Data:** cache files only; the database is untouched.

# Cross-track impact

- None.

# Implementation notes

- One card: the live run sits between writing the gate and writing parsers
  against real pages, and a split would park the parsers behind a review cycle.
- Two manifests, two runs: schedule pages first, because the thirty game ids
  are chosen from them. URLs that might not exist yet go last, since a run stops
  at its first failure; a failed entry is fixed in the manifest and the rerun
  costs only the gap.
- Live runs set `SCRAPER_USER_AGENT` for the process to
  `nba-data-project/0.1 (+https://github.com/alejandrou/NBA_ML-.)` — a real
  contact that is not a personal e-mail address; `.env` is not touched.
- Cache writes go through the new public `scraping/cache_writer.py`, the same
  atomic, never-overwrite writer. The two private copies in the existing
  acquisition modules stay as they are, so no Basketball Reference path changes;
  switching them to the shared writer is a later cleanup.
- Generalizing nothing: the new command carries its own copy of the gate and
  the existing ones are untouched (AGENTS.md, "Live-scraping approval gate").

## Progress

- 2026-09-23 — Offline tooling built and tested before any live request.
- 2026-09-23 — The first live run was refused by the session's permission
  classifier; the owner's general delegation did not count as the direct
  instruction AGENTS.md requires. No request was made.
- 2026-09-23 — On the owner's direct instruction ("run the F8-001 live pilot")
  both manifests ran: 84 requests, no failure, no 429. The thirty games were
  chosen from the cached schedule pages between the two runs.
- 2026-09-23 — The real pages corrected three assumptions:
  - schedules do not mark playoffs, so game type moved to the box score heading;
  - Cup games put a label before the scorebox date, so the venue is read after
    the date line;
  - the reconciliation now allows team turnovers, per-line minute rounding, a
    0:00 line without plus-minus, and inactive players in events.
  The synthetic parser fixtures were replaced by trimmed real pages.
- 2026-09-23 — Review fixes, four findings:
  - the report passed with no game when only the schedule manifest was given;
    it now fails closed, and so does a game whose box score or linked
    play-by-play the manifests leave out;
  - line-score rows of different lengths raised `ValueError`; they now fail
    the play-by-play period checks;
  - blank player cells were summed as zeros, so a missing turnover column
    passed as team turnovers; blanks are now missing;
  - the cache writer checked and then replaced, and its rollback could delete
    another writer's body. It now publishes with a primitive that refuses an
    existing target, and rolls back only the file it published.
  Rerun over the real cache: 29 of 30 games, every check and detail unchanged.

# Durable knowledge updates

- `docs/decisions/0019-*` — per-game data comes from Basketball Reference.
- `docs/ml/PREDICTOR_PLAN.md` — the chosen provider, pages, and measured cost.
- `docs/validation/PER_GAME_ACQUISITION_PILOT.md` — the pilot record.

# Review evidence

## Automated validation

- Command: `uv run pytest tests/unit/test_game_pilot_manifest.py tests/unit/test_game_pilot_acquisition.py tests/unit/test_league_schedule_parser.py tests/unit/test_box_score_parser.py tests/unit/test_play_by_play_parser.py tests/unit/test_game_pilot_validation.py tests/unit/test_rate_limited_client.py`
- Result: 171 passed.
- Command: `uv run pytest tests/unit/test_nba_team_season_acquisition.py tests/unit/test_player_page_acquisition.py tests/unit/test_backfill_manifest.py tests/unit/test_cache_inventory.py tests/unit/test_stats_coverage_artifact.py`
- Result: 102 passed — the existing acquisition gates and cache discovery are unchanged.
- Command: `uv run ruff check .`
- Result: all checks passed.
- Command: `uv run mypy src/nba_data`
- Result: no issues in 77 source files.
- Command: `uv run pytest`
- Result: 1,157 passed, 27 skipped (integration tests without a database).
- Command: `uv run python scripts/validate_tasks.py`
- Result: task validation passed.
- Live, on the owner's direct instruction of 2026-09-23:
  - Command: `acquire-game-pilot` on `F8-001-game-pilot-schedules-20260923.json`
  - Result: 24 fetched, 24 requests, 0 failures, 0 rate-limited, 144 s.
  - Command: `acquire-game-pilot` on `F8-001-game-pilot-games-20260923.json`
  - Result: 60 fetched, 60 requests, 0 failures, 0 rate-limited, 371 s.
- Offline over the acquired cache:
  - Command: `uv run nba-data validate game-pilot` over both manifests and both
    acquisition reports.
  - Result: 29 of 30 games pass. Exit 1 is expected: `200010310ATL` has a source
    line score with two quarters swapped, confirmed against the page's
    play-by-play and quarter boxes (pilot record, finding 1). Rerun after the
    review fixes: every check and detail unchanged.
  - Command: the same, with only the schedule manifest.
  - Result: exit 1, `"games": 0`, `"coverage_problems": ["the manifests name no game"]`.

## Manual happy path

1. `uv run nba-data acquisition dry-run-game-pilot tasks/manifests/F8-001-game-pilot-games-20260923.json`
2. `uv run nba-data validate game-pilot --manifest tasks/manifests/F8-001-game-pilot-schedules-20260923.json --manifest tasks/manifests/F8-001-game-pilot-games-20260923.json --acquisition-report reports/f8-001/acquisition-schedules.json --acquisition-report reports/f8-001/acquisition-games.json --output reports/f8-001/validation.json`
3. Compare `reports/f8-001/validation.json` with the tables in
   `docs/validation/PER_GAME_ACQUISITION_PILOT.md`.

Expected result: step 1 reports 60 cache hits and 0 estimated fetches, with no
network access. Step 2 reports 30 games, 29 passed, `failed_games`
`["200010310ATL"]`, and exits 1. The per-game checks match the pilot record.
Both commands need the cache at `data/raw/html` from this machine; the
`--acquisition-report` files exist only here under `reports/`.

## Manual sad path

1. `uv run nba-data acquisition acquire-game-pilot tasks/manifests/F8-001-game-pilot-games-20260923.json`
   (no flags).
2. Copy that manifest, set `"approved_by_owner": false`, and run
   `uv run nba-data acquisition dry-run-game-pilot <copy>`.
3. Rerun the step 2 happy-path command with `--cache-root` pointing at an
   empty folder. Never delete real cache files: refetching one is a live
   request.
4. Rerun the step 2 happy-path command with only the schedule manifest.

Expected result:
- Step 1 prints `Refusing acquisition without --owner-approved and
  --execute-approved-manifest` and exits 1 without reading the manifest.
- Step 2 fails with `manifest.approved_by_owner must be true` (exit 2).
- Step 3 names the missing page per game and exits 1.
- Step 4 exits 1 with `"games": 0` and
  `"coverage_problems": ["the manifests name no game"]`.
- None of them makes a request.

## Known limitations

- `validate game-pilot` exits 1 on the pilot's own manifests because of the
  documented source error in `200010310ATL`; there is deliberately no allow-list.
- Identity is checked against the cache as the mirror of `core`, not by
  querying the database.
- Play-by-play cannot yet support lineups or possessions: changes between
  periods are unlogged, and `pbpstats` does not read these pages (Stage 4).
- Neutral sites are not derived; the venue is recorded for F8-002 to decide.
- The two older acquisition modules keep their private copies of the cache
  writer, which check and then replace: safe for one sequential command, not
  for two processes writing the same page. Only `scraping/cache_writer.py`
  publishes without replacing; moving them onto it is a later cleanup.
- `.env` still holds the placeholder `SCRAPER_USER_AGENT`. The live runs set a
  contact for the process only; set a real one before Stage 2.
