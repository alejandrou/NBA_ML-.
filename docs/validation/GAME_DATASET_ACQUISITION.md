# Game Dataset Acquisition (Stage 2)

How to plan, approve, batch, and resume the Stage 2 acquisition of league
schedule and box-score pages for 2014-15 to 2025-26 (`docs/ml/PREDICTOR_PLAN.md`,
ADR 0020). The tooling is F8-004; the live runs and the disposable load are
F8-006; the load into `nba` is F8-018. The F8-001 pilot
(`PER_GAME_ACQUISITION_PILOT.md`) measured the cost: 14,442 box scores, roughly
25 hours at the six-second floor, plus the schedule pages. F8-006's manifests
hold 114 schedule URLs: 6 season pages plus 108 month pages (the other six
season pages were already cached).

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

## The F8-006 run, 2026-10-25 to 2026-10-28

The owner authorized every live run of the card on 2026-10-25 (*"Do them
yourself i give you permission as the owner of the project"*, in reply to the
plan of season pages, month pages, then box scores season by season). The
instruction is quoted in each manifest's `approval_basis`. The 30 approved
manifests are
`tasks/manifests/F8-006-NBA_<year>-{season-page,schedule-months,box-scores}-20261025.json`:
six season pages (the other six were already cached), twelve month-page
manifests, and twelve box-score manifests: 114 schedule URLs (6 season pages
plus 108 month pages) and 14,442 box scores. After the run,
`dry-run-game-season` reports every URL of all 30 as a cache hit.

### Timeline

| UTC | Event |
|---|---|
| 10-25 17:57 | Schedule run 1: six season pages, 6 requests |
| 10-25 18:00–18:09 | Schedule run 2: twelve seasons' month pages, 95 requests |
| 10-25 18:10 | Box scores start, newest season first, `--max-fetches 550` |
| 10-25 19:52 | Stopped: `[Errno 11001] getaddrinfo failed` on `202602250DEN` after a ten-minute hang — the local network, not the source. Resumed on the owner's instruction |
| 10-25 23:05 | Stopped by the owner (2025-26 and 2024-25 complete) |
| 10-26 17:38–23:36 | Resumed and stopped by the owner (through 2022-23) |
| 10-27 16:07–23:26 | Resumed and stopped by the owner (through 2018-19) |
| 10-28 16:10–23:20 | Resumed; every season `completed: true` |

No 429 was received. No page took more than one request, and every response was
HTTP 200. Each stop either ended at a batch boundary or killed a batch in
flight. A killed batch writes no report, so the figures below come from the
cache metadata (`fetched_at`, the gzip size trailer), not from the batch
reports. After every stop the cache held no temp file and no body without its
metadata.

The batches were run back to back by a small driver outside the repository. It
waited at least seven seconds between `acquire-game-season` processes, because
the client spaces requests only within one process. It stopped on any non-zero
exit, and checked for a `reports/f8-006/STOP` file before each batch.

### Per season

Requests are live requests for that season's box scores; 2025-26 includes the
one failed request. Bytes are uncompressed / cached (`.html.gz`) MiB. Wall is the
time spent fetching, excluding the stops. *Line-score warnings* are
`line_score_disagrees`. *Neutral* is the number of games flagged `neutral_site`
(see "Neutral sites" for the four seasons marked *deferred*).

| Season | Schedule requests | Box-score requests | MiB | Wall | Expected | Loaded | Quarantined | Line-score warnings | Players created | Neutral | Player lines |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2014-15 | 8 | 1,227 | 556 / 69.3 | 2.13 h | 1,230 | 1,230 | 0 | 1 | 2 | 2 | 36,306 |
| 2015-16 | 10 | 1,230 | 558 / 69.5 | 2.15 h | 1,230 | 1,230 | 0 | 0 | 0 | 2 | 36,550 |
| 2016-17 | 10 | 1,230 | 558 / 69.5 | 2.15 h | 1,230 | 1,229 | 1 | 1 | 0 | deferred | 36,657 |
| 2017-18 | 10 | 1,230 | 557 / 69.5 | 2.15 h | 1,230 | 1,227 | 3 | 5 | 6 | deferred | 40,579 |
| 2018-19 | 10 | 1,230 | 558 / 69.6 | 2.15 h | 1,230 | 1,230 | 0 | 0 | 5 | 3 | 40,396 |
| 2019-20 | 7 | 1,056 | 479 / 59.8 | 1.85 h | 1,059 | 1,059 | 0 | 0 | 3 | 91 | 35,219 |
| 2020-21 | 7 | 1,078 | 492 / 61.0 | 1.88 h | 1,080 | 1,080 | 0 | 3 | 0 | 0 | 35,671 |
| 2021-22 | 10 | 1,230 | 557 / 69.6 | 2.15 h | 1,230 | 1,230 | 0 | 3 | 6 | 0 | 41,950 |
| 2022-23 | 10 | 1,230 | 558 / 69.6 | 2.15 h | 1,230 | 1,228 | 2 | 1 | 1 | deferred | 40,856 |
| 2023-24 | 6 | 1,226 | 558 / 69.5 | 2.14 h | 1,231 | 1,230 | 1 | 4 | 3 | deferred | 43,398 |
| 2024-25 | 6 | 1,228 | 559 / 69.7 | 2.15 h | 1,231 | 1,231 | 0 | 1 | 5 | 8 | 43,421 |
| 2025-26 | 7 | 1,228 | 561 / 69.7 | 2.15 h | 1,231 | 1,231 | 0 | 3 | 8 | 8 | 43,306 |
| **Total** | **101** | **14,423** | **6,552 / 816** | **25.2 h** | **14,442** | **14,435** | **7** | **22** | **39** | | **474,309** |

Twenty box scores were already cached (archive and the F8-001 pilot), so 14,422
pages were fetched. The schedule pages add 35 MB uncompressed, 5.6 MB cached,
and about 11 minutes. Every page took 6.2–6.5 s, as the pilot measured.

### The load — disposable database, 2026-10-28

`nba_f8006_tmp` is a `pg_dump`/`pg_restore` copy of `nba`, which is at
`0009_games_and_box_scores` (applied 2026-10-24, `MIGRATION_HEAD_HANDOVER.md`)
with the 2000-2026 archive loaded and empty game tables. `nba` was only read.
The command is the one in "Rerunning it from the cache", with `--output
reports/f8-006/disposable/run1` (and `run2`).

| Run | Exit | Wall | Result |
|---|---:|---:|---|
| 1 | 1 | 31 min | 14,435 loaded, 7 quarantined, `missing_box_score` 0 in every season, 39 players created |
| 2 (rerun) | 1 | 29 min | 14,435 `unchanged`, the same 7 quarantined, 0 players created, 0 neutral-site updates |

Both runs exit 1 only because of the quarantines. The database then holds 14,435
games, 28,870 team rows, 474,309 player rows (32.9 a game), and 2,693 players
(2,654 + 39). `game_types` shows `regular_season` and exactly three `cup_final`
(2023-24 to 2025-26); there is no other heading.

### Quarantines — source errors

Each page's own player rows disagree with its team-total row. This was checked
by a second, independent parse of the cached HTML, which gives the same numbers.
The minutes rule allows half a second of rounding per played line (F8-005). They
stay quarantined.

| Game | Code | The page |
|---|---|---|
| `201703250LAC` | `minutes_mismatch` | LAC players sum to 239:53; team total 240 |
| `201711110UTA` | `minutes_mismatch` | BRK 239:20 and UTA 239:21; totals 240 |
| `201712040NOP` | `minutes_mismatch` | GSW 241:24; total 240 |
| `201711240DEN` | `player_sum_mismatch` | DEN player turnovers sum to 21; team total 20 |
| `202212250DEN` | `minutes_mismatch` | DEN 264:55; total 265 (one overtime) |
| `202303020GSW` | `minutes_mismatch` | GSW 239:48; total 240 |
| `202311210PHI` | `minutes_mismatch` | CLE 264:55; total 265 (one overtime) |

### Warnings

- `line_score_disagrees`, 22 games: a quarter's points in the box score differ
  from the line score by 1–3 points (the final scores agree). Stored as loaded.
  The games are listed in the per-season reports.
- `cup_final_plus_minus_zeros`, `202312090LAL` (the 2023-24 Cup final): every
  plus-minus is 0 on the page; stored as NULL.
- `neutral_site_deferred` in 2016-17, 2017-18, 2022-23, and 2023-24 (below).

### Neutral sites

Flagged games in the eight complete seasons: Mexico City and London (2014-15,
2015-16, 2018-19); 91 in 2019-20 — the 88 bubble games at Bay Lake, 2 in
Mexico City, and 1 in Paris; none in 2020-21 and 2021-22; Mexico City, Paris,
Berlin, London, the Cup semifinals and final in Las Vegas, and the Spurs'
Austin games (2024-25, 2025-26).

The loader infers neutral sites only when every selected game of the season is
loaded. A quarantined game is never loaded, so the four seasons with
quarantines keep `neutral_site = NULL` for all their 4,914 games. Running the
same city rule read-only over those seasons (owner, 2026-10-29) decides every
game, with no undetermined game and no warning, and flags 17:

| Season | Games | Venue |
|---|---|---|
| 2016-17 | `201701120DEN` | London |
| 2016-17 | `201701120PHO`, `201701140PHO` | Mexico City |
| 2017-18 | `201712070BRK`, `201712090BRK` | Mexico City |
| 2017-18 | `201801110PHI` | London |
| 2022-23 | `202212170SAS` | Mexico City |
| 2022-23 | `202301190DET` | Paris |
| 2022-23 | `202304060SAS`, `202304080SAS` | Austin |
| 2023-24 | `202311090ORL` | Mexico City |
| 2023-24 | `202312070LAL`, `202312070MIL` (Cup semifinals), `202312090LAL` (Cup final) | Las Vegas |
| 2023-24 | `202401110CLE` | Paris |
| 2023-24 | `202403150SAS`, `202403170SAS` | Austin |

F8-016 makes the loader infer them: a season whose only unloaded games were
quarantined in the same run is inferred; a missing box score still defers.
With it, the twelve seasons hold 131 neutral games.

**Austin** (owner, 2026-10-29): the city rule stays unchanged, so the Spurs'
Austin games are neutral — 8 games from 2022-23 to 2025-26. No venue is
hard-coded as an exception.

### Players created

The 39 players with box-score lines and no cached player page, by season:
`roberro01`, `youngpa01` (2014-15); `griffer01`, `johnsja04`, `nashle01`,
`ouattya01`, `thornma02`, `youngmi02` (2017-18); `bibbsju01`, `bluietr01`,
`evanske01`, `phillta01`, `prestbi01` (2018-19); `pointsi01`, `randole01`,
`wooteke01` (2019-20); `ellisma01`, `holmaar01`, `hommeda01`, `smithch07`,
`stewadj02`, `tillmju01` (2021-22); `lewisju02` (2022-23); `bediach01`,
`galloja01`, `ricesi01` (2023-24); `armstta02`, `buiebo01`, `mccoyja01`,
`steveer01`, `stewadj01` (2024-25); `batesta01`, `djurini01`, `keyty01`,
`mangaky01`, `mcgloga01`, `ndiayel01`, `sorbeth01`, `tooheal01` (2025-26).

Read-only on the loaded copy (2026-10-29): of 2,693 players, 2,654 have a
`core.player_seasons` row and these 39 have none. All 39 have
`stats.player_game_totals` rows (1 to 82 each), none played a second (inactive
or did-not-play roster lines), and none has a NULL Basketball Reference ID.
`smithch07` and `thornma02` share a name with `smithch05` (Chris Smith) and
`thornma01` (Marcus Thornton) but are different people.

`validate offline-database` pins `core.players` at 2,654. Before F8-017 the
loaded copy therefore failed with one issue, `core.players has 2693 rows;
expected 2654`, and nothing else. F8-017 applies the owner's rule (2026-10-29):
the pinned 2,654 counts only players with a `player_season`, and every other
player must have at least one `stats.player_game_totals` row. Rerun on the
loaded copy (2026-10-30), the validator exits 0 with no issue and reports
`core.players` 2,654, `core.players_without_player_seasons` 39 and
`core.players_total` 2,693. F8-018 can
now validate `nba` after the games load.

### Persistent database

F8-006 ends at the disposable load (owner, 2026-10-29). Loading `nba` is
F8-018, after F8-016 and F8-017 are merged, each step from merged `origin/main`
on a new explicit owner instruction, recorded here in the order they run:

1. Revision `0009` applied to `nba` — done on 2026-10-24
   (`MIGRATION_HEAD_HANDOVER.md`), before F8-006. F8-018 applies no migration.
2. `backfill games` for 2015–2026 against `nba`, with `--require-complete
   --output reports/f8-018/nba-load`, and a rerun — pending (F8-018).
3. `validate offline-database` passing on `nba` afterwards — pending (F8-018).

## Rerunning it from the cache

Nothing needs fetching. Every F8-006 manifest is a cache hit:

```bash
for f in tasks/manifests/F8-006-*.json; do uv run nba-data acquisition dry-run-game-season "$f"; done
```

Then load the twelve seasons into a **disposable** database at `0009` with
the archive loaded, such as `nba_f8006_tmp` (a `pg_dump`/`pg_restore` copy of
`nba`). The load is idempotent: a rerun reports every game `unchanged`.

Do not rely on the normal configuration: `.env` selects `nba`. Override
`DATABASE_URL` in the shell (an environment variable takes precedence over
`.env`), check read-only through that same configured connection which database
it selects, and stop unless it is `nba_f8006_tmp`:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://nba:nba@localhost:5432/nba_f8006_tmp"
$db = uv run python -c "from sqlalchemy import text; from nba_data.db.session import create_db_engine; print(create_db_engine().connect().execute(text('select current_database()')).scalar_one())"
if ($db -ne "nba_f8006_tmp") { throw "DATABASE_URL selects '$db', not nba_f8006_tmp: stop." }
uv run nba-data backfill games --execute-approved-games-backfill --season 2015 --season 2016 --season 2017 --season 2018 --season 2019 --season 2020 --season 2021 --season 2022 --season 2023 --season 2024 --season 2025 --season 2026 --require-complete --output reports/f8-006/games
uv run nba-data validate offline-database --backfill-report reports/f8-003/nba-load/offline-backfill.json
Remove-Item Env:DATABASE_URL
```

Run every command in the same shell as the check, and clear the override
afterwards. Expect the backfill to exit 1 with exactly the seven quarantines
above until the source pages change.

This procedure never targets `nba`. Loading `nba` is F8-018 ("Persistent
database" above): its own commands, from merged `origin/main`, on a new
explicit owner instruction.
