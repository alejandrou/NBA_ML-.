---
id: F8-004
title: Plan and gate the Stage 2 game acquisition
track: data
areas:
  - scraping
  - testing
  - documentation
priority: 98
depends_on:
  - F8-001
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/validation/PER_GAME_ACQUISITION_PILOT.md
  - docs/decisions/0020-take-per-game-data-from-basketball-reference.md
  - docs/decisions/0004-rate-limited-scraping.md
  - src/nba_data/scraping/game_pilot_manifest.py
  - src/nba_data/scraping/game_pilot_acquisition.py
  - src/nba_data/scraping/cache_writer.py
  - src/nba_data/scraping/parsers/league_schedule.py
  - src/nba_data/config/settings.py
  - src/nba_data/cli/main.py
validation:
  - uv run pytest tests/unit/test_game_season_manifest.py tests/unit/test_game_season_planning.py tests/unit/test_game_season_acquisition.py tests/unit/test_game_pilot_manifest.py tests/unit/test_game_pilot_acquisition.py tests/unit/test_rate_limited_client.py tests/unit/test_cache_inventory.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None in this card. It builds and tests the tooling offline; every live run it enables belongs to F8-006 and needs the owner's direct instruction.
---

# Goal

Give Stage 2 a gated, resumable way to acquire twelve seasons of schedule and
box-score pages (2014-15 to 2025-26: ~108 schedule pages, ~14,440 box scores,
~25 hours at the six-second floor) in batches the owner approves one at a time,
with the game list derived offline from cached schedule pages, never guessed.

# Evidence and current state

- The only per-game acquisition is the pilot's: `acquire-game-pilot` runs one
  approved manifest of at most `MAX_PILOT_URLS = 100` explicit URLs
  (`scraping/game_pilot_manifest.py:33`, `:170-173`). One season is ~1,230 box
  scores.
- `acquire_game_pilot_manifest` (`game_pilot_acquisition.py:227`) is
  cache-first, sequential, stops on the first failure, and reports per-page
  requests, bytes, and wall time. Cache writes go through
  `scraping/cache_writer.py`, which never overwrites.
- `parse_league_schedule_page` returns games and `month_links`
  (`parsers/league_schedule.py:99-123`); `ScheduleGame.play_in` reads the
  "Play-In Game" note.
- Pilot findings: schedules never mark playoffs (2); the NBA Cup final looks
  like any Cup game on the schedule (3); month URLs must be read from the season
  page, e.g. 2019-20's `-october-2019` and `-october-2020` (13).
- `Settings.scraper_user_agent` only refuses a blank value
  (`config/settings.py:35-41`). The worktree's `.env` carries a real contact
  since 2026-10-18, but a fresh worktree or a deleted `.env` falls back to the
  placeholder default, which this card's guard refuses.
- Box-score cache files are `unsupported_path` to `cache_inventory.py`, which
  every existing backfill skips (ADR 0020).

# Human decisions or resources

- [x] **A new manifest kind and command, not a bigger pilot.** The pilot's
      100-URL ceiling stays as it is. Stage 2 gets its own manifest contract
      with its own ceiling, flags, and refusal messages (the gate is copied,
      never generalized or weakened — AGENTS.md).
- [x] **One season per box-score manifest**, ≤ 1,400 URLs. A season is the
      approval unit: about 2.1 hours, twelve approvals in all.
- [x] **Schedules before box scores, both planned offline.** The season pages
      are planned from fixed URLs; the month pages from the cached season pages'
      `month_links`; the box scores from the cached month pages.
- [x] **Game selection**: played regular-season rows plus the NBA Cup final.
      With a play-in row in the season, every played row dated before the first
      play-in date; without one (2014-15 to 2018-19), each team's first 82
      played rows. The planner fails closed when the count differs from a
      reviewed per-season table: 1,230, except 1,059 (2019-20), 1,080
      (2020-21), and 1,231 for 2023-24 to 2025-26 (the Cup final row). The
      heading of every fetched page is confirmed by the loader (F8-005).
- [x] **Batches inside a season**: `--max-fetches N` stops a run cleanly after N
      live requests (a run of ~550 is about an hour). Rerunning resumes from the
      cache.
- [x] **The new command refuses the placeholder user agent** — a stricter guard
      on the new command only; the existing commands are untouched.
- [x] **Play-by-play is not acquired** — Stage 4 (F8-015).

# Acceptance criteria

- `scraping/game_season_manifest.py`: a manifest of one season's
  `league_schedule` or `box_score` URLs (one page type per manifest), validated
  like the pilot's — `status: approved`, `approved_by_owner: true`, aware
  `approved_at`, `approval_basis`, cache-first/sequential/stop-on-first-failure
  policy, ≤ 10 requests/minute, write target `HtmlCache .html.gz` — plus every
  entry in the manifest's season and the 1,400-URL ceiling. Draft manifests
  (`status: draft`, `approved_by_owner: false`) load for planning and dry runs
  and are refused by the acquire command.
- `scraping/game_season_planning.py` (offline, no client):
  - `plan-game-schedules --season <end year>` writes a draft with the season
    page when it is not cached, otherwise with every month page its
    `month_links` name.
  - `plan-game-box-scores --season <end year>` reads only cached schedule
    pages, fails when a month page the season page names is missing, applies the
    selection rule, checks the count table, and writes a draft of the season's
    box-score URLs.
  - Unit tests cover play-in and no-play-in seasons, 2019-20's two October
    pages, unplayed and postponed rows, the Cup-final row, a count mismatch, and
    a missing month page.
- CLI: `nba-data acquisition plan-game-schedules`, `plan-game-box-scores`,
  `dry-run-game-season`, and `acquire-game-season <manifest>
  --owner-approved --execute-approved-manifest [--max-fetches N] [--output]`.
  Without both flags it prints the refusal and exits 1 before reading the
  manifest; with the placeholder user agent it refuses; on a 429 it stops.
- `--max-fetches` counts live requests only. Cache hits are free; the report
  says `stopped_reason: max_fetches` and exits 0.
- The report carries per-page status, requests, bytes, wall time, cache hits,
  and totals, like the pilot report.
- The pilot's manifest, command, and tests are unchanged; `cache_inventory.py`
  still classifies box-score and schedule files as `unsupported_path`.
- Every test is offline (fake client); no network in the suite.

# Scope

`src/nba_data/scraping/game_season_manifest.py`, `game_season_planning.py`,
`game_season_acquisition.py` (new); `src/nba_data/cli/main.py` (four commands);
`tests/unit/test_game_season_*.py` (new); `tests/fixtures/html/` (trimmed
fixtures from already-cached pages only); `docs/validation/PER_GAME_ACQUISITION_PILOT.md`
("Running Stage 2" section) or a new `docs/validation/GAME_DATASET_ACQUISITION.md`.

# Out of scope

- Any live request (F8-006).
- Play-by-play, playoffs, play-in, and the 2026-27 season.
- The loader and the game tables (F8-002, F8-005).
- Changing the pilot, team-season, or player-page acquisition commands.

# Impact

- **CLI:** four new `acquisition` commands.
- **Cache:** none until F8-006 runs them.

# Cross-track impact

- None.

# Implementation notes

- The fetch loop may reuse `acquire_game_pilot_manifest`'s internals only if the
  pilot's behaviour and tests stay byte-for-byte the same; otherwise copy it.
- Season of a game = the `season_end_year` of the schedule page listing it,
  never derived from the date (2020 bubble overlap).
- Write drafts under `reports/` (never committed). F8-006 copies an approved
  manifest into `tasks/manifests/` when the owner approves it.
- If the count table is wrong for a season, correct it from the cached pages
  with the evidence in the card. Never loosen the check.

# Durable knowledge updates

- `docs/validation/` — how to plan, approve, batch, and resume a Stage 2 season.

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
