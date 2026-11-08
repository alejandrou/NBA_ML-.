---
id: F8-020
title: Build bounded current-season catch-up
track: data
areas:
  - scraping
  - testing
  - documentation
priority: 88
depends_on:
  - F8-013
read:
  - docs/validation/CURRENT_SEASON_REFRESH.md
  - src/nba_data/scraping/current_season_manifest.py
  - src/nba_data/scraping/current_season_planning.py
  - src/nba_data/scraping/current_season_acquisition.py
  - src/nba_data/scraping/game_season_manifest.py
  - src/nba_data/scraping/client.py
  - src/nba_data/scraping/cache_writer.py
  - src/nba_data/scraping/parsers/box_score.py
  - tests/unit/test_current_season_acquisition.py
validation:
  - uv run pytest tests/unit/test_current_season_catch_up_manifest.py tests/unit/test_current_season_catch_up.py
  - uv run pytest tests/unit/test_current_season_manifest.py tests/unit/test_current_season_planning.py tests/unit/test_current_season_acquisition.py tests/unit/test_game_season_manifest.py tests/unit/test_game_season_acquisition.py tests/unit/test_game_pilot_acquisition.py tests/unit/test_rate_limited_client.py
  - uv run nba-data acquisition plan-current-season-catch-up --help
  - uv run nba-data acquisition dry-run-current-season-catch-up --help
  - uv run nba-data acquisition acquire-current-season-catch-up --help
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - uv run python scripts/validate_tasks.py
critical_actions:
  - None during offline implementation. Approving any catch-up manifest is the owner's decision, per batch, and every live catch-up batch requires the owner's direct current instruction (F8-008).
---

# Goal

Let F8-008 recover when more than 150 scored games have no archived box score,
through a separate path of explicit, individually approved, bounded batches,
without weakening the current-season refresh safety interlock.

# Evidence and current state

- `plan_box_scores` raises above the manifest's ceiling and nothing is trimmed,
  so `acquire-current-season` stops with `plan_refused` at phase `box_score`.
  `--max-fetches` does not affect planning, so reruns make no progress.
- That refusal comes after the season, month, and team phases have written their
  snapshots (`test_a_ceiling_exceeded_stops_before_any_box_score`), so one
  refused refresh is a sufficient bootstrap: catch-up never fetches a schedule.
- `dry-run-current-season` raises on the same ceiling, so today nothing reports
  the size of a backlog above it offline.
- `validate_game_season_manifest` accepts only seasons 2015 through 2026, and
  `STAGE_2_SEASON_END_YEARS` must not change.
- `BasketballReferenceClient` counts every attempt, retries included, against
  `max_requests` and checks it before each attempt. It retries a 5xx twice by
  default; with `max_429_retries=0` the first 429 raises.
- `validate_html_for_cache` only checks the document prefix, and an archived box
  score is never requested again, so a 200 error page would count as coverage
  permanently and falsify the remaining-backlog figure.
- `require_latest_month_pages` already fails closed on a missing or empty month.

# Human decisions or resources

- [x] **Approach**: keep the 150-page ceiling and every refusal; add a separate
      path, as the F8-013 review recommended. Each batch is its own approved
      manifest of explicit URLs; a standing refresh approval never covers one.
- [x] **Manifest kind**: `current_season_box_score_catch_up`, box scores of
      `CURRENT_SEASON_END_YEAR` only. See the contract below.
- [x] **Batch contract**: at most 150 URLs and 150 live requests, retries
      included, ordered by `(game_date, game_id)`. Batches carry no sequence
      number: each draft takes the oldest games still missing.
- [x] **Command surface**: `plan-`, `dry-run-` and
      `acquire-current-season-catch-up`, mirroring the Stage 2 commands.
- [x] **Page identity**: catch-up checks it before publishing, because a batch
      archives up to 150 immutable pages and its report claims coverage. F8-021
      still owns the refresh path and the recovery of bad cache entries.

# Contract

**Backlog.** Every game that is `played` in `require_latest_month_pages` and has
no archived box score, sorted by `(game_date, game_id)`. It is enumerated without
any ceiling, by new code; `plan_box_scores` is not changed. A game listed on two
month snapshots is an error, as in `plan_box_scores`.

**Manifest** (new module `src/nba_data/scraping/current_season_catch_up_manifest.py`):

```json
{
  "manifest_id": "F8-020-NBA_2027-catch-up-<first_game_id>-<n>-draft-<YYYYMMDD>",
  "kind": "current_season_box_score_catch_up",
  "status": "draft",
  "approved_by_owner": false,
  "approved_at": null,
  "approval_basis": null,
  "scope": {
    "season_end_year": 2027,
    "page_type": "box_score",
    "max_urls": 150,
    "max_live_requests": 150
  },
  "backlog_at_draft": {"missing_box_scores": 412, "remaining_after_batch": 262},
  "acquisition_policy": {
    "cache_first": true,
    "sequential": true,
    "stop_on_first_failure": true,
    "requests_per_minute": 10,
    "max_requests_per_minute": 20,
    "archive_write_target": "HtmlCache .html.gz"
  },
  "entries": [
    {
      "page_type": "box_score",
      "url": "https://www.basketball-reference.com/boxscores/202610200OKC.html",
      "season_end_year": 2027,
      "game_id": "202610200OKC",
      "reason": "2026-10-20 HOU at OKC, scored on the latest october snapshot"
    }
  ]
}
```

Limits: `1 <= len(entries) <= max_urls <= 150` and
`len(entries) <= max_live_requests <= 150`. Entries are unique and strictly
ascending by `(game_date, game_id)`. `requests_per_minute` is at most 10,
`max_requests_per_minute` at most 20. Approval has the same fields and rules as
the refresh manifest. The URL must be exactly the box-score URL of its `game_id`,
whose date falls in the season window and whose home code is not synthetic.

**Commands** (`nba-data acquisition`):

| Command | Behavior |
|---|---|
| `plan-current-season-catch-up [--batch-size N] [--output PATH]` | Offline. Writes a draft of the N oldest missing games (1 to 150, default 150), default path under `reports/current-season/`, never overwriting. Prints the backlog count. An empty backlog writes nothing and exits 2. |
| `dry-run-current-season-catch-up MANIFEST [--output PATH]` | Offline; draft or approved. Prints per-entry cached or to-fetch, the backlog before and the expected remainder, and the minimum duration. Exits 2 on any contract refusal. |
| `acquire-current-season-catch-up MANIFEST --owner-approved --execute-approved-manifest [--max-fetches N] [--output PATH]` | One batch. The client gets `max_requests=min(max_fetches, max_live_requests)`, `max_429_retries=0`, `follow_redirects=False`. |

Exit codes match `acquire-current-season`: 1 before the manifest is read when a
flag is missing, and on `rate_limited` or `failed`; 2 on a refusal before any
request; 0 on success and on a clean budget stop.

**Before the first request**, `acquire` refuses (exit 2) a draft, a wrong kind, a
placeholder `SCRAPER_USER_AGENT`, a pace above 10/minute or above the manifest's,
incomplete month snapshots, or an entry that is not `played` on the latest
snapshots. An entry already archived is a cache hit, not a refusal.

**Before publishing a body**: `validate_html_for_cache`, then
`parse_box_score_page` must yield both teams, with the home code and visitor code
equal to the snapshot row's. Other parser issues do not block, since optional
stats are not prerequisites. A mismatch stops the batch as `failed` and archives
nothing. Bodies go only through `write_html_to_cache_safely`.

**Report**: the fields of the refresh report without `phase`, plus
`max_live_requests` and `coverage`: `scored_games`, `archived`, `missing_before`,
`missing_after`, `next_game_id`. Coverage is computed offline after the batch,
also when it stops; if that computation fails, `coverage` is `null` with
`coverage_error`, never zeros.

# Acceptance criteria

- `validate_current_season_catch_up_manifest` enforces every limit above; each
  violation has a test: 151 entries, `max_live_requests` of 151 or below
  `len(entries)`, wrong kind, season 2026, duplicates, unsorted entries, an
  off-site or mismatched URL, a synthetic home code, a draft claiming approval.
- An approved catch-up manifest is refused by the refresh, Stage 2, and pilot
  validators; a refresh manifest is refused by the catch-up validator.
- With 151 and with 400 missing games the planner writes a draft of the 150
  oldest in `(game_date, game_id)` order, identical across repeated calls and
  whatever the month order; `--batch-size` is honored; 0 and 151 are refused; an
  empty backlog and a missing month snapshot are refused; an existing output
  file is never replaced.
- Reruns reduce the backlog: draft, acquire, and re-plan over 400 missing games
  ends with 250 and then 100 `missing_after`, and the next draft starts at
  `next_game_id`. A rerun of a finished batch sends no request.
- Request budget: no run sends more than `max_live_requests` attempts, 5xx
  retries included, proven with the real client over a mock transport. Spending
  it stops cleanly with `stopped_reason: max_fetches`, exit 0, and a rerun
  resumes; `--max-fetches` only lowers the budget.
- A 429 stops at once: exactly one attempt for that URL, none after it, the
  partial report carries `retry_after_seconds` and `coverage`, exit 1.
- Missing either flag exits 1 before the manifest is read and creates no client.
  Every pre-request refusal above exits 2 and creates no client.
- A 200 error page, a page of another game, and a failed archive write each stop
  the batch, leave nothing in the archive, and leave `missing_after` unchanged
  for that game; a corrected rerun succeeds.
- The refresh's constants, `plan_box_scores`, its refusal tests, the Stage 2 and
  pilot contracts, and `tasks/manifests/` are unchanged; the existing tests named
  in `validation:` pass without edits.
- `docs/validation/CURRENT_SEASON_REFRESH.md` has an actionable procedure:
  bootstrap with one refresh that ends in `plan_refused`, count with the planner,
  review the draft, approve per batch, run on the owner's instruction, repeat,
  return to the refresh once the backlog fits its ceiling. It covers 429 and
  budget recovery, and Known limitations no longer calls this future work.

# Scope

New `current_season_catch_up_manifest.py` and `current_season_catch_up.py` under
`src/nba_data/scraping/`, three new commands in `src/nba_data/cli/main.py`, their
tests, and `docs/validation/CURRENT_SEASON_REFRESH.md`.

# Out of scope

Live acquisition and database writes. Changes to existing gates, ceilings, or
commands. Edits to `tasks/manifests/`. Team or schedule page catch-up. Page
validation of the refresh path and repair of existing cache entries (F8-021).

# Impact

- New `nba-data acquisition` commands and one new manifest kind. F8-008 can use
  them for its catch-up batches.

# Cross-track impact

- None.

# Implementation notes

- Copy guard code rather than generalizing it, as `current_season_manifest.py`
  and `current_season_acquisition.py` do; do not alter the originals.
- `scope.page_type` is deliberately singular and `archive_write_target` is not
  `write_target`: together with the season check, these keep the Stage 2 and
  pilot validators from accepting this kind. The cross-validator tests pin it.
- The schedule fixture helpers in `tests/unit/test_current_season_acquisition.py`
  generate any number of games. Build valid box-score bodies from
  `tests/fixtures/html/box_score_202008170DEN_trimmed.html` with the team codes
  replaced. No test may touch the network.
- Backlog size is never inferred from a date; only the planner reports it.

# Durable knowledge updates

- `docs/validation/CURRENT_SEASON_REFRESH.md`.

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
