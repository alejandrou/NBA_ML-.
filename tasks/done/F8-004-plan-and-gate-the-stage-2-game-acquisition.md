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
`tests/unit/test_game_season_*.py` (new); `scraping/client.py` and
`tests/unit/test_rate_limited_client.py` (opt-in request budget and redirect
policy needed to enforce the new command's limits); `tests/fixtures/html/` (trimmed
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

- Command: `uv run pytest tests/unit/test_game_season_manifest.py tests/unit/test_game_season_planning.py tests/unit/test_game_season_acquisition.py tests/unit/test_game_pilot_manifest.py tests/unit/test_game_pilot_acquisition.py tests/unit/test_rate_limited_client.py tests/unit/test_cache_inventory.py`
- Result: 198 passed (91 new: 31 manifest, 19 planning, 38 acquisition/CLI,
  3 client budget).
- Command: `uv run ruff check .` — All checks passed.
- Command: `uv run mypy src/nba_data` — no issues in 90 source files.
- Command: `uv run pytest` — 1371 passed, 250 skipped (the PostgreSQL lanes, no
  database configured), 0 failed.
- Command: `uv run python scripts/validate_tasks.py` — passed after the move.
- Offline smoke run against the real cache: `plan-game-schedules --season 2020`
  planned the 10 month pages, both Octobers included (3 cached);
  `plan-game-box-scores --season 2024` failed closed, naming the 6 uncached
  month pages; `dry-run-game-season` on the draft reported 3 hits, 7 misses,
  36 s; `acquire-game-season` on it without flags refused, exit 1. No request
  was made.

## Manual happy path

1. `uv run nba-data acquisition plan-game-schedules --season 2024 --output reports/game-season/try-2024-months.json`
2. `uv run nba-data acquisition dry-run-game-season reports/game-season/try-2024-months.json`
3. Open the draft and check `status: draft`, `approved_by_owner: false`, nine
   `NBA_2024_games-<month>.html` entries, and the `planning` block.

Expected result: the plan prints the season's months and `cached_pages: 3`; the
dry run prints 3 hits, 6 misses, and `estimated_minimum_seconds: 30.0`. Nothing
is fetched and the cache is unchanged.

## Manual sad path

1. Rerun step 1 above: it refuses with "already exists" and leaves the draft
   untouched.
2. `uv run nba-data acquisition plan-game-box-scores --season 2024`: it fails
   and names the uncached month pages.
3. `uv run nba-data acquisition acquire-game-season reports/game-season/try-2024-months.json --owner-approved --execute-approved-manifest`:
   it refuses the draft ("manifest.status must be 'approved'") before creating a
   client; without the two flags it refuses before reading the manifest, exit 1.

Expected result: every step exits non-zero, no request is made, and nothing is
written to the cache.

## Known limitations

- The count table (1,230 / 1,059 / 1,080 / 1,231) comes from the F8-001 pilot
  record and the card; no Stage 2 season is fully cached yet, so it can only be
  confirmed by the first `plan-game-box-scores` in F8-006. A mismatch fails the
  plan rather than passing.
- The season page repeats its first month, and the planner also plans that
  month's own page (one extra request per season), as the card specifies.
- `parse_league_schedule_page` drops the year of a month link, so the planner
  trusts that the season page links only its own months (true on every cached
  page).

## Branch re-review (2026-10-25)

Reviewed the complete uncommitted implementation against `origin/main` and the
acceptance criteria. Two issues remain open:

1. **P2: `--max-fetches` is not a hard request ceiling.** The check in
   `game_season_acquisition.py` runs outside `client.fetch`, while the central
   client retries 5xx responses internally. Offline reproduction with the real
   client, `httpx.MockTransport`, responses 500/500/200, and `max_fetches=1`
   made three HTTP attempts and reported `live_request_count: 3`. The existing
   retry test spends two requests against a limit of two, so it misses this
   boundary. Enforce the remaining budget before each HTTP attempt and cover
   retries when only one request remains. The limitation recorded above does
   not satisfy the card's stated request limit.
2. **P2: dry-run duration ignores the manifest's approved pace.** An approved
   one-request/minute manifest with four missing pages and the default
   ten-request/minute settings reports 18 seconds, although the approved pace
   requires at least 180 seconds. Acquisition rejects those same settings.
   Derive the estimate from the slower of the configured and approved rates,
   or refuse the incompatible settings consistently; cover a slower manifest
   in the dry-run tests.

Validation repeated during review:

- Focused command from `validation`: **182 passed**.
- `uv run pytest`: **1355 passed, 250 skipped**, 7 dependency deprecation
  warnings; PostgreSQL lanes remain unverified without a configured database.
- `uv run ruff check .`: passed.
- `uv run mypy src/nba_data`: passed, 90 source files.
- `uv run python scripts/validate_tasks.py`: passed.
- `uv run python scripts/validate_tasks.py --all-worktrees`: passed.
- `git diff --check`: passed.

Both reproductions used disposable caches and fake clients or mocked HTTP;
no external request or persistent database action was performed. The card
remains in review with these findings open; implementation files are unchanged
by this re-review.

## Fixes for the re-review (2026-10-25)

1. **Hard request ceiling.** `BasketballReferenceClient` takes an opt-in
   `max_requests` (default `None`, so every existing command is unchanged) and
   raises `RequestBudgetExhaustedError` before any HTTP attempt, 429 and 5xx
   retries included, that would pass it. `acquire-game-season` builds its client
   with `max_requests=--max-fetches`; the acquisition treats the error as a clean
   `max_fetches` stop (exit 0), records the requests the page spent, and leaves
   it uncached for the next run. `remaining_entries` now counts every page not
   yet in the cache. This edits `scraping/client.py`, outside the card's stated
   scope, because the retries live there. Tests: the real client with
   `MockTransport` returning 500s and `max_fetches=1` sends exactly one request;
   a retry with one request left stops cleanly; the client budget stops at
   500/500 with a budget of 2; a client without a budget still retries.
2. **Dry-run pace.** The estimate uses the slower of the configured pace and the
   manifest's `requests_per_minute`. Test: four missing pages at an approved
   1 request/minute with default settings estimate 180 s.

## Follow-up review of the fixes (2026-10-25)

The earlier 5xx retry-budget and dry-run pace cases now pass. The focused
validation command passes all 188 tests. Ruff, mypy, all-worktree task
validation, and `git diff --check` also pass.
The full suite passes: 1361 passed, 250 skipped (PostgreSQL lanes), with 7
dependency deprecation warnings.

One additional P2 remains in `scraping/client.py`: automatic redirects run
inside `httpx.Client.get`, below the request counter, request-budget check, and
rate limiter. With the real BasketballReferenceClient, a MockTransport returning
302 then 200, `follow_redirects=True` (the production default), and
`max_requests=1`, two HTTP requests were made at the same fake-clock timestamp
while the acquisition reported `live_request_count: 1`. The second URL was not
an entry in the manifest. Thus the retry fix works, but the hard request ceiling
and six-second spacing still do not cover redirected requests. This behavior
predates the new budget; the new budget's guarantee must account for it.

For gated acquisition, refuse redirects or handle each allowed redirect through
the same URL checks, budget, and rate limiter. Add a mocked redirect regression
case that asserts transport calls, spacing, and reported request count. No live
requests were made during this reproduction; implementation files were not
modified by this review.

## Final resolution and closure (2026-10-25)

All three review findings are resolved. Stage 2 now constructs its client with
`follow_redirects=False`, independently of whether a request budget is set.
The client exposes this as an opt-in override while preserving the existing
redirect policy for other callers. HTTPX refuses redirect responses through
`raise_for_status`; the acquisition records a failed partial report and leaves
the page uncached. No redirect target is requested.

Ten offline regression cases cover HTTP 301, 302, 303, 307, and 308, each with
no batch limit and with a one-request limit. They assert one transport call,
one reported request, a failed partial report, correct remaining-page count,
and no cache body or metadata. CLI tests also assert redirects are disabled.

Final validation:

- The card's focused pytest command: **198 passed**.
- `uv run pytest`: **1371 passed, 250 skipped**, 7 dependency deprecation
  warnings. PostgreSQL integration remains a CI check; no database was used.
- `uv run ruff check .`: passed.
- `uv run mypy src/nba_data`: passed, 90 source files.
- Both `uv run python scripts/validate_tasks.py` and its `--all-worktrees`
  variant passed after the move to `done/`; `git diff --check` also passed.

No remaining actionable review findings. Full-season acquisition and confirmation
of the count table remain F8-006 work under its separate live-run approval gate.
The owner explicitly requested moving this card to done, committing, pushing,
and preparing the branch for a pull request. No live acquisition or database
operation was performed. No cross-track handoff targets F8-004, and no parked
card bookkeeping is needed.
