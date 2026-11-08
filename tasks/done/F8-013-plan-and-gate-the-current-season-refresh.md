---
id: F8-013
title: Plan and gate the current-season refresh
track: data
areas:
  - scraping
  - testing
  - documentation
priority: 89
depends_on:
  - F8-004
  - F8-012
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/validation/PER_GAME_ACQUISITION_PILOT.md
  - docs/decisions/0004-rate-limited-scraping.md
  - src/nba_data/scraping/game_season_manifest.py
  - src/nba_data/scraping/game_season_planning.py
  - src/nba_data/scraping/game_season_acquisition.py
  - src/nba_data/scraping/snapshot_cache.py
  - src/nba_data/scraping/parsers/league_schedule.py
  - src/nba_data/cli/main.py
validation:
  - uv run pytest tests/unit/test_current_season_manifest.py tests/unit/test_current_season_planning.py tests/unit/test_current_season_acquisition.py tests/unit/test_game_season_manifest.py tests/unit/test_game_season_acquisition.py tests/unit/test_game_pilot_acquisition.py tests/unit/test_rate_limited_client.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None in this card. It builds and tests the tooling offline with a fake client; every live refresh belongs to F8-008 and later runs, each on the owner's direct instruction.
---

# Goal

One gated, bounded command that refreshes the in-progress season: its schedule
pages and, once, its team pages as snapshots (F8-012), and the box scores of
games that have finished since the last refresh, in one run the owner orders
with one instruction.

# Evidence and current state

- F8-004 builds the Stage 2 gate: a manifest kind of explicit URLs, `status:
  approved`, `approved_by_owner: true`, `--owner-approved
  --execute-approved-manifest`, `--max-fetches`, stop on 429, and the
  placeholder user-agent refusal. Its URL lists are explicit because a
  completed season is known in advance.
- An in-progress season is not: which box scores exist depends on the schedule
  fetched in the same refresh. Two manifests and two approvals per refresh would
  make a daily refresh cost two instructions.
- F8-012 stores mutable pages as snapshots; `CURRENT_SEASON_END_YEAR = 2027`.
- A daily refresh is about 3 schedule pages and 10–15 box scores (~2 minutes at
  the six-second floor); the first one also takes 30 team pages (~3 minutes).

# Human decisions or resources

- [x] **Manual, on the owner's instruction, every run** (decided 2026-10-18,
      F8-008). No scheduler, no standing approval in `AGENTS.md`. Measured first;
      a standing approval would be a later `shared` card.
- [x] **A standing, bounded manifest per season**: `current_season_refresh`, a
      new kind, approved once by the owner for season 2027. It does not list
      URLs; it approves a fixed rule with ceilings: the season page; month pages
      the season snapshot links; the 30 team pages of the season, only while
      missing; box scores of games that have a score in the latest month
      snapshots and no cached box score. Ceilings per run: 20 schedule pages,
      30 team pages, 150 box scores, ≤ 10 requests/minute. The approval of the
      manifest never authorizes a run; each run still needs both flags and the
      owner's direct instruction. The existing manifest kinds are untouched.
- [x] **Which month pages a run refetches** (`--as-of YYYY-MM-DD`, required, no
      clock read): the month of `as-of`, the next one, and any earlier month
      whose latest snapshot shows a game dated before `as-of` without a score.
      A month never fetched is always fetched.
- [x] **Order inside one run**: season page → month pages → team pages → box
      scores planned from the snapshots just written. A failure stops the run;
      rerunning resumes, because box scores are cache-first and schedule pages
      are new snapshots.
- [x] **Command**: `nba-data acquisition dry-run-current-season <manifest>
      --as-of D` (offline: prints the plan from the latest snapshots, counting
      box scores only for scores already seen) and
      `acquire-current-season <manifest> --as-of D --owner-approved
      --execute-approved-manifest [--max-fetches N] [--output]`.

# Acceptance criteria

- `scraping/current_season_manifest.py`: loads and validates the kind (season
  equals `CURRENT_SEASON_END_YEAR`, the ceilings above and no larger, policy and
  pace fields as F8-004's); a draft loads for the dry run and is refused by the
  acquire command.
- `scraping/current_season_planning.py` (offline): month selection as decided,
  from `month_links` of the latest season snapshot; box-score selection from
  the latest month snapshots (played rows with a game link, not in the archive
  cache); stops with an error when a ceiling would be exceeded, never trims.
- `scraping/current_season_acquisition.py`: writes schedule and team pages only
  through `SnapshotCache.write`, box scores only through
  `write_html_to_cache_safely`; sequential; ≥ 6 s apart; stop on 429 honouring
  `Retry-After`; `--max-fetches` counts live requests only; report like
  F8-004's with `phase` per page.
- CLI refusals, each tested: no flags (exits 1 before reading the manifest), a
  draft, a season other than 2027, the placeholder user agent, a ceiling
  exceeded.
- Tests (fake client, fixtures trimmed from cached pages): first run (season,
  months, 30 team pages, box scores); a second run on a later `as-of` fetches
  only new months and new box scores and no team page; a month with a late
  score; a postponed row; a 429 mid-run.
- `docs/validation/CURRENT_SEASON_REFRESH.md` (new): how to draft and approve
  the manifest, the exact command for one refresh, and how to resume.

# Scope

`src/nba_data/scraping/current_season_*.py` (new), `cli/main.py` (two
commands), `tests/unit/test_current_season_*.py` (new), `tests/fixtures/html/`
(trimmed from cached pages only), `docs/validation/CURRENT_SEASON_REFRESH.md`.

Review scope clarification: `scraping/client.py` adds optional
`RateLimitExceededError.retry_after_seconds` metadata needed by this command's
429 report. Existing retry and pacing behavior is unchanged; the mocked real
client test covers propagation into the refresh report.

# Out of scope

Any live request. Loading (F8-014). Seasons other than the current one.
Play-by-play. Changing F8-004's, the pilot's, or the archive's commands.

# Impact

- Two new `acquisition` commands.

# Cross-track impact

- None.

# Implementation notes

- Copy F8-004's guard code rather than generalizing it (`AGENTS.md`).
- Write the draft manifest to `reports/`; F8-008 copies the approved one into
  `tasks/manifests/` when the owner approves it.

# Durable knowledge updates

- `docs/validation/CURRENT_SEASON_REFRESH.md` (new).

# Review evidence

## Automated validation

- Command: `uv run pytest tests/unit/test_current_season_manifest.py tests/unit/test_current_season_planning.py tests/unit/test_current_season_acquisition.py tests/unit/test_game_season_manifest.py tests/unit/test_game_season_acquisition.py tests/unit/test_game_pilot_acquisition.py tests/unit/test_rate_limited_client.py`
- Result after review fixes: 179 passed (67 current-season tests, including
  three new regressions for malformed month recovery and out-of-season rows).
- Command: `uv run ruff check .` — All checks passed.
- Command: `uv run mypy src/nba_data` — no issues in 108 source files.
- Command: `uv run pytest` — after review fixes: 1766 passed, 258 skipped,
  0 failed, 7 dependency deprecation warnings (238.17 s). PostgreSQL integration
  checks remain skipped without their disposable test environment.
- Command: `uv run python scripts/validate_tasks.py` — passed after the move.
- Review rerun: `uv run python scripts/validate_tasks.py --all-worktrees` —
  passed; data has F8-013 in review, app has no in-progress card.
- Review rerun: `git diff --check`, `uv run ruff check .`, and
  `uv run mypy src/nba_data` — passed.
- Offline smoke: the draft was written to
  `reports/current-season/NBA_2027_current-season-refresh.draft.json` and
  `dry-run-current-season ... --as-of 2026-11-07` printed a 1-fetch plan
  (no snapshots exist yet). No live request was made.

## Manual happy path

1. Write the draft with the one-liner in `docs/validation/CURRENT_SEASON_REFRESH.md`
   (or reuse the one already in `reports/current-season/`).
2. `uv run nba-data acquisition dry-run-current-season reports/current-season/NBA_2027_current-season-refresh.draft.json --as-of 2026-11-07`
3. `uv run pytest tests/unit/test_current_season_acquisition.py -k "first_run or later_run" -v`

Expected result: step 2 exits 0 and prints `status: draft`, `planned` =
`{season: 1, month: null, team: null, box_score: 0}`; step 3 shows the first
run fetching season → 7 months → 30 team pages → 15 box scores in that order,
and the second run fetching only 3 months and 18 new box scores, no team page.

## Manual sad path

1. `uv run nba-data acquisition acquire-current-season reports/current-season/NBA_2027_current-season-refresh.draft.json --as-of 2026-11-07`
2. Same command plus `--owner-approved --execute-approved-manifest`.
3. Same as 2 with `--as-of 2026-11-7`.

Expected result: 1 exits 1 with "Refusing acquisition without --owner-approved
and --execute-approved-manifest"; 2 exits 2 with "manifest.status must be
'approved'" (or the placeholder user-agent error if `SCRAPER_USER_AGENT` is
unset); 3 exits 2 with "--as-of must be a YYYY-MM-DD date". None creates a
client or sends a request.

## Known limitations

- **150 box-score ceiling vs. catch-up.** Above the manifest's ceiling the run
  cannot progress, and `--max-fetches` cannot split its plan. Preserve the
  interlock; F8-020 designs separate bounded catch-up and is now a prerequisite
  of F8-008. Stage 2 cannot bootstrap 2027 unchanged. Count the actual backlog
  from snapshots rather than claiming a particular date guarantees overflow.
- Team pages and box scores still have only generic HTML validation. HTTP 200
  error HTML can become permanent cached coverage; F8-021 defines page-type
  and identity checks before publication.
- A request budget consumed by recurring schedule fetches makes no downstream
  progress on rerun. The runbook now explains this and requires checking the
  report's completion fields even after exit 0.
- No new HTML fixture file: tests build month pages from the cached
  `league_schedule_2027_trimmed.html`, replacing only its rows in the page's own
  row markup.
- The draft is written by a `python -c` one-liner, not a CLI command, to keep
  the card's two commands.
- Postponed rows without a score keep their month refetched every run.

## Branch review fixes (2026-11-07)

- Reject malformed schedule responses before writing snapshots: previously a
  bad month snapshot stopped the next run during planning, before the month
  could be fetched again. Regression proves the old snapshot survives and a
  rerun completes.
- Reject game dates outside the current season window both on publication and
  when planning from existing snapshots, before they authorize box-score URLs.
- Accept the optional client exception metadata as a justified scope addition;
  retain existing fixture reuse and the offline draft-writing one-liner.
- No live request, approved-manifest edit, or Git mutation during review.
