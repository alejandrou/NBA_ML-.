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
