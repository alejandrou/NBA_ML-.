# Game Dataset Acquisition (Stage 2)

How to plan, approve, batch, and resume the Stage 2 acquisition of league
schedule and box-score pages for 2014-15 to 2025-26 (`docs/ml/PREDICTOR_PLAN.md`,
ADR 0020). The tooling is F8-004; the live runs are F8-006. The F8-001 pilot
(`PER_GAME_ACQUISITION_PILOT.md`) measured the cost: about 108 schedule pages
and 14,442 box scores, roughly 25 hours at the six-second floor.

Every live run needs the owner's direct instruction naming it. A manifest's
approval records what may be fetched; it never authorizes a run by itself.

## The approval unit

One manifest is one season and one page type, at most 1,400 URLs. A season
takes three manifests, each approved on its own:

| Step | Manifest | Pages | Time |
|---|---|---:|---:|
| 1 | the season page | 1 | seconds |
| 2 | the month pages the season page links | 7–10 | about a minute |
| 3 | the season's box scores | 1,059–1,231 | about 2.1 hours |

The URLs are never guessed. Month URLs are read from the cached season page
(2019-20 has `-october-2019` and `-october-2020`); box-score URLs from the cached
month pages.

## Which games are selected

Played rows only (a box-score link and both scores). The schedule pages do not
mark playoff games, so the planner selects by date:

- **With a play-in row in the season** (2019-20 onwards): every played row
  dated before the first play-in game. The NBA Cup final, played in December,
  is included.
- **Without one** (2014-15 to 2018-19): each team's first 82 played rows. A
  game inside one team's 82 and outside the other's fails the plan.

The count must equal the reviewed table in `scraping/game_season_planning.py`:
1,230 per season, except 1,059 (2019-20), 1,080 (2020-21), and 1,231 for
2023-24 to 2025-26 (the Cup final). A mismatch fails the plan; correct the table
only from the cached pages, with the evidence on a card. The loader (F8-005)
confirms every page's heading.

The planner also fails when a month page the season page links is not cached,
when a cached schedule page does not parse cleanly, when a game is listed on two
month pages, or when the season page lists a game no month page lists.

## Planning (offline)

```powershell
uv run nba-data acquisition plan-game-schedules --season 2024
uv run nba-data acquisition plan-game-box-scores --season 2024
uv run nba-data acquisition dry-run-game-season reports/game-season/NBA_2024_box-scores.draft.json
```

Drafts are written under `reports/game-season/` (`NBA_<year>_season-page`,
`_schedule-months`, `_box-scores`), never committed, and never overwritten:
move an old draft away, or pass `--output`. Run `plan-game-schedules` once for
the season page and again, after it is cached, for the month pages. A draft
carries `status: draft` and `approved_by_owner: false`; `dry-run-game-season`
reads it and reports cache hits, misses, and the minimum duration at the slower
of the configured pace and the pace the manifest approves.

## Approving

The owner approves a draft by copying it into `tasks/manifests/` and setting:

```json
"manifest_id": "F8-006-NBA_2024-box-scores-<yyyymmdd>",
"status": "approved",
"approved_by_owner": true,
"approved_at": "<ISO-8601 timestamp with a timezone>",
"approval_basis": "<who approved what, and when>"
```

Nothing else changes. The contract (`scraping/game_season_manifest.py`) also
requires one season and one page type for every entry, cache-first, sequential,
stop-on-first-failure, at most 10 requests/minute, and the `HtmlCache .html.gz`
write target.

## Running a batch

With a real contact in `SCRAPER_USER_AGENT` (the command refuses the
placeholder default and any `example.com` contact):

```powershell
uv run nba-data acquisition acquire-game-season tasks/manifests/<manifest>.json --owner-approved --execute-approved-manifest --max-fetches 550 --output reports/game-season/<manifest>-batch-1.json
```

- Without both flags the command refuses and exits 1 before reading the
  manifest. A draft, a faster pace than the manifest approves, or more than 10
  requests/minute are refused before any client is created.
- `--max-fetches N` stops cleanly once N live requests are spent (550 is about
  an hour): `stopped_reason: max_fetches`, exit 0. The client checks the limit
  before every HTTP attempt, 5xx retries included, so a run never sends more
  than N requests; a page whose retry would pass N is left uncached for the next
  run.
- A 429 or any other failure stops the run at once with a partial report
  (`stopped_reason: rate_limited` or `failed`) and exits 1. After a 429, wait
  before the next batch.
- Redirects are refused: only the explicit approved URL is requested. A
  redirect stops the run with a failed partial report and leaves the page
  uncached, with no request to the redirect target.
- The report lists every page's status, requests, bytes, compressed bytes, and
  wall time, and totals for the run.

## Resuming

Rerun the same command. Pages already cached are cache hits, which cost no
request and do not count toward `--max-fetches`; the run continues at the first
missing page. Cache writes never overwrite a file. A season is done when a run
reports `completed: true`.

The new pages share `data/raw/html/basketball-reference/` with the archive.
`cache_inventory.py` classifies them as `unsupported_path`, which every existing
backfill skips.
