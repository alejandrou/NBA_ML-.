# Per-Game Acquisition Pilot

Stage 1 of `docs/ml/PREDICTOR_PLAN.md` (card F8-001): prove on thirty games that
schedule, results, box scores, and play-by-play from Basketball Reference
(ADR 0019) can be acquired, cached, parsed offline, and reconciled, and measure
what that costs. The live runs were made on 2026-09-23 on the owner's direct
instruction. This record cannot be reproduced without contacting Basketball
Reference again; the reconciliation can, from the cache.

## Verdict

| Data | Go / no-go | Why |
|---|---|---|
| Schedule and results | **Go** | 24 of 24 pages parsed with no issue, upcoming games included; every pilot game found with the same teams and final score as its box score. |
| Team and player box scores | **Go** | 30 of 30 parsed with no issue; final score agrees across five sources; player lines sum to team totals; every game type classified from the heading. |
| Play-by-play: events and scoring | **Go** | Present for every game back to 1999–2000; final score, periods, and every player's points reconcile; per-period points reconcile in 29 of 30 (the 30th is a source error, below). |
| Play-by-play: lineups and possessions | **Not yet** | Lineup changes between periods are never logged, and `pbpstats` does not read these pages. Stage 4 needs its own period-start lineup inference or an NBA.com pilot. |

**Recommendation for Stage 2:** league schedule month pages for the calendar and
results, and one box score page per regular-season game — about 14,550
requests, roughly 25 hours at the six-second floor, resumable. Defer
play-by-play (another ~25 hours) to Stage 4.

## What was acquired

| Manifest | Pages | Requests | Failures | 429s | Wall time | Decoded | Compressed |
|---|---:|---:|---:|---:|---:|---:|---:|
| `F8-001-game-pilot-schedules-20260923` | 24 schedule | 24 | 0 | 0 | 144 s | 8.3 MB | 1.3 MB |
| `F8-001-game-pilot-games-20260923` | 30 box score + 30 play-by-play | 60 | 0 | 0 | 371 s | 22.5 MB | 3.3 MB |
| **Total** | 84 | 84 | 0 | 0 | 515 s | 30.8 MB | 4.6 MB |

No retry happened: requests equal pages. Per page, including the enforced
six-second spacing:

| Page | Decoded | Compressed | Wall time (mean, max) |
|---|---:|---:|---:|
| League schedule (one month) | 338 KiB | 53 KiB | 6.02 s, 6.30 s |
| Box score | 479 KiB | 58 KiB | 6.09 s, 6.38 s |
| Play-by-play | 253 KiB | 49 KiB | 6.27 s, 6.39 s |

A game costs two requests and about 12.6 seconds; its two pages take about
107 KiB in the cache.

## How the thirty games were chosen

From the cached schedule pages, by the rule on the F8-001 card: each season's
opening game, its longest overtime game in the fetched months, and its edge
cases. The list and each game's reason are in the games manifest.

- **Eras:** 1999–2000 through 2025–26; the defunct `CHH` and `CHA` codes.
- **Overtime:** one, two, and three overtimes.
- **Neutral and foreign sites:** Tokyo, Mexico City (twice), Paris, the 2020
  bubble, and Las Vegas NBA Cup games.
- **Game types:** regular season, NBA Cup group and knockout games, three Cup
  finals, two play-in games, three playoff games.
- **Unusual circumstances:** the 2020-03-11 suspension night, empty-arena
  2020–21 games, and the most recent season, which the archive does not hold.

## Reconciliation

`nba-data validate game-pilot` over both manifests: **29 of 30 games pass**. The
command exits 1 because of the one source error, which is the behaviour a
loader gate needs.

| Check | Passed | Other |
|---|---:|---|
| Box score and play-by-play parse without issue | 30 | |
| Schedule row found; teams agree; play-in note agrees with heading | 30 | |
| Final score: schedule = scorebox = team totals = line score = play-by-play | 30 | |
| Line-score periods match the schedule's overtime marker and the play-by-play | 30 | |
| Points per period: play-by-play = line score | 29 | 1 failed: source error |
| Every scoring event credits the player the box score credits | 30 | |
| Every player an event names is on the box score | 30 | |
| Player lines sum to team totals (team turnovers apart) | 30 | |
| Minutes sum to the game length (within rounding) | 30 | |
| Five starters per team; no player listed twice | 30 | |
| Plus-minus balances to five times the margin | 28 | 1 not published (2025 Cup final), 1 published as all zeros (2023 Cup final) |
| Team codes resolve to `core.team_seasons` | 24 | 6 expected gaps: 2025–26 is not archived |
| Player ids resolve to `core.players` | 22 | 8 expected gaps: 2025–26 players, and two inactive-only players |

### Per game

| Game | Season | Type | Result | Periods | Venue | PBP events | Subs | Same-clock sub groups | Replay reviews | Carry-over conflicts | Outcome |
|---|---:|---|---|---:|---|---:|---:|---:|---:|---:|---|
| `199911050SAC` | 2000 | regular season | MIN 95 @ SAC 100 | 4 | Tokyo Dome, Tokyo | 518 | 44 | 9 | 0 | 11 | passed |
| `200010310ATL` | 2001 | regular season | CHH 106 @ ATL 82 | 4 | Philips Arena, Atlanta | 448 | 44 | 7 | 0 | 16 | **failed**: period points |
| `200011010CLE` | 2001 | regular season | SAC 100 @ CLE 102 | 6 | Gund Arena, Cleveland | 530 | 40 | 2 | 0 | 6 | passed |
| `200910270CLE` | 2010 | regular season | BOS 95 @ CLE 89 | 4 | Quicken Loans Arena, Cleveland | 455 | 55 | 9 | 0 | 14 | passed |
| `200910300CHA` | 2010 | regular season | NYK 100 @ CHA 102 | 6 | Time Warner Cable Arena, Charlotte | 533 | 39 | 4 | 0 | 14 | passed |
| `201410280NOP` | 2015 | regular season | ORL 84 @ NOP 101 | 4 | Smoothie King Center, New Orleans | 511 | 50 | 10 | 0 | 7 | passed; gap: inactive-only player |
| `201411190BRK` | 2015 | regular season | MIL 122 @ BRK 118 | 7 | Barclays Center, Brooklyn | 575 | 57 | 11 | 0 | 15 | passed |
| `201411120MIN` | 2015 | regular season | HOU 113 @ MIN 101 | 4 | Mexico City Arena, Mexico City | 467 | 49 | 9 | 0 | 6 | passed |
| `201910220TOR` | 2020 | regular season | NOP 122 @ TOR 130 | 5 | Scotiabank Arena, Toronto | 568 | 49 | 12 | 0 | 9 | passed |
| `202003110DAL` | 2020 | regular season | DEN 97 @ DAL 113 | 4 | American Airlines Center, Dallas | 431 | 39 | 9 | 1 | 10 | passed |
| `202007300NOP` | 2020 | regular season | UTA 106 @ NOP 104 | 4 | HP Field House, Bay Lake | 495 | 48 | 11 | 0 | 10 | passed |
| `202008170DEN` | 2020 | playoffs | UTA 125 @ DEN 135 | 5 | HP Field House, Bay Lake | 491 | 51 | 10 | 1 | 8 | passed |
| `202012220BRK` | 2021 | regular season | GSW 99 @ BRK 125 | 4 | Barclays Center, Brooklyn | 516 | 41 | 10 | 0 | 10 | passed |
| `202012260DET` | 2021 | regular season | CLE 128 @ DET 119 | 6 | Little Caesars Arena, Detroit | 565 | 56 | 13 | 2 | 13 | passed |
| `202105180IND` | 2021 | play-in | CHO 117 @ IND 144 | 4 | Bankers Life Fieldhouse, Indianapolis | 476 | 39 | 8 | 3 | 8 | passed |
| `202310240DEN` | 2024 | regular season | LAL 107 @ DEN 119 | 4 | Ball Arena, Denver | 447 | 55 | 13 | 0 | 6 | passed |
| `202311030POR` | 2024 | regular season (Cup group) | MEM 113 @ POR 115 | 5 | Moda Center, Portland | 519 | 51 | 13 | 3 | 13 | passed |
| `202311090ORL` | 2024 | regular season | ATL 120 @ ORL 119 | 4 | Mexico City Arena, Mexico City | 515 | 49 | 10 | 4 | 10 | passed |
| `202312070MIL` | 2024 | regular season (Cup semifinal) | IND 128 @ MIL 119 | 4 | T-Mobile Arena, Las Vegas | 495 | 45 | 6 | 0 | 8 | passed |
| `202312090LAL` | 2024 | Cup final | IND 109 @ LAL 123 | 4 | T-Mobile Arena, Las Vegas | 544 | 65 | 8 | 4 | 16 | passed; gap: plus-minus all zero |
| `202410220BOS` | 2025 | regular season | NYK 109 @ BOS 132 | 4 | TD Garden, Boston | 387 | 39 | 10 | 1 | 8 | passed |
| `202412170OKC` | 2025 | Cup final | MIL 97 @ OKC 81 | 4 | T-Mobile Arena, Las Vegas | 464 | 54 | 12 | 3 | 14 | passed; gap: inactive-only player |
| `202501230IND` | 2025 | regular season | SAS 140 @ IND 110 | 4 | Accor Arena, Paris | 440 | 57 | 12 | 2 | 16 | passed |
| `202504190IND` | 2025 | playoffs | MIL 98 @ IND 117 | 4 | Gainbridge Fieldhouse, Indianapolis | 466 | 56 | 12 | 4 | 7 | passed |
| `202510210OKC` | 2026 | regular season | HOU 124 @ OKC 125 | 6 | Paycom Center, Oklahoma City | 583 | 67 | 13 | 6 | 20 | passed; gaps: 2025–26 |
| `202512180DEN` | 2026 | regular season | ORL 115 @ DEN 126 | 4 | Ball Arena, Denver | 451 | 47 | 11 | 1 | 12 | passed; gaps: 2025–26 |
| `202512160NYK` | 2026 | Cup final | SAS 113 @ NYK 124 | 4 | T-Mobile Arena, Las Vegas | 498 | 58 | 11 | 2 | 14 | passed; gaps: 2025–26; no plus-minus |
| `202604120SAS` | 2026 | regular season | DEN 128 @ SAS 118 | 4 | Frost Bank Center, San Antonio | 473 | 44 | 12 | 1 | 12 | passed; gaps: 2025–26 |
| `202604140CHO` | 2026 | play-in | MIA 126 @ CHO 127 | 5 | Spectrum Center, Charlotte | 527 | 84 | 20 | 4 | 13 | passed; gaps: 2025–26 |
| `202604180CLE` | 2026 | playoffs | TOR 113 @ CLE 126 | 4 | Rocket Arena, Cleveland | 483 | 66 | 12 | 5 | 14 | passed; gaps: 2025–26 |

Every game cost two requests and 12.4–12.7 seconds; the first game of the run
shows 6.6 seconds because its box score was the run's first request.

## Findings

Each of these changes how the Stage 2 loader or schema must behave.

1. **One line score is wrong at the source.** In `200010310ATL` the line score
   gives Charlotte 33 and 23 points in the third and fourth quarters. The
   play-by-play (73–62 at the end of the third) and the page's own quarter box
   scores say 23 and 33. The final score agrees everywhere. Period scores must
   be reconciled before they are loaded, and a conflict quarantined, never
   silently resolved.
2. **Schedule pages never mark playoff games.** There is no separator row and no
   note. Only play-in games carry a note ("Play-In Game"). The box score heading
   is the reliable classifier:
   - a plain "\<Visitor\> at \<Home\> Box Score" is the regular season;
   - otherwise a prefix names the type: "Play-In Game:", "\<year\> NBA
     \<round\> Game \<n\>:", or "In-Season Tournament Final:" / "NBA Cup Final:".
   Stage 2 can exclude playoff rows before fetching, from the first play-in date
   or each team's 82nd game, and must confirm every fetched heading.
3. **The NBA Cup final is not a regular-season game and is marked only by its
   heading.** On the schedule it looks like any other Cup game ("In-Season
   Tournament" in 2023–24, "NBA Cup" since). The Cup knockout games before the
   final count, including neutral-site Las Vegas semifinals. Plus-minus for the
   final differs by year: 0 for every player in 2023, real values in 2024, none
   in 2025. The zeros must be stored as missing.
4. **No page flags a neutral site.** Schedule notes say "at Tokyo, Japan" or
   "at Paris, France" in some seasons but not for the 2025 Paris games, the 2020
   bubble, or Las Vegas. The box score heading says "vs" only for some of them.
   The venue line ("Accor Arena, Paris, France") is always present;
   `core.games.neutral_site` has to be derived from it against each team's home
   venue, or curated.
5. **Team totals carry team turnovers.** Turnovers not credited to any player
   (0–3 per team-game, mean 0.85) sit only in the team total. Every other
   counter sums exactly. `stats.team_game_totals` must keep the team's own
   total, not a sum of player rows.
6. **Minutes are rounded to the second per player.** A team's player seconds
   miss the game length (240 minutes plus 25 per overtime) by up to half a
   second per line; the team total is exact.
7. **Attendance has two empty values.** Blank (not published, e.g. the 2020
   bubble) and 0 (no fans, 2020–21) are different and must stay different.
8. **Participation.** Across the pilot: 653 played lines, 129 "Did Not Play",
   7 "Did Not Dress", 1 "Not With Team", and 180 inactive-list entries with no
   line at all. Zero points with minutes is a played line, and so is a line
   with 0:00 played (Bismack Biyombo in `202311030POR`), whose plus-minus is
   blank.
9. **`core.players` misses inactive-only players.** Patric Young
   (`youngpa01`, 2014–15 Pelicans) and Nikola Topić (`topicni01`, 2024–25
   Thunder) appear in box score inactive lists but only in their team page's
   salaries table, which the team-season loader does not read. Every player
   with a box score line in the archived seasons resolves. Stage 2 must create
   players from box score links (stable Basketball Reference ids) or let
   inactive entries reference unresolved ids.
10. **2025–26 is not in `core`.** It has no `core.seasons` or
    `core.team_seasons` rows, and each 2025–26 game names two to seven players
    `core` does not hold.
11. **Play-by-play shape.**
    - 387–583 events per game.
    - Simultaneous substitutions in every game: 2–20 same-clock groups, kept in
      feed order.
    - Replay reviews appear in 2019–20 and later games ("Instant Replay
      (Challenge: Ruling Stands)"; the first in the pilot is from March 2020),
      and in no earlier game.
    - Fouls sit in the column of the team that drew them, so an event's column
      is not always its actor's team.
    - Some team events name no player ("Violation by Team").
    - An inactive player can appear: Damian Lillard, inactive, drew a technical
      foul in `202504190IND`.
12. **Lineups between periods are not logged.** Carrying each period's closing
    lineup into the next contradicts a logged substitution 6–20 times per game
    (mean 11.3), always after the first period. Lineup and possession
    reconstruction needs period-start inference. `pbpstats` reads NBA.com
    formats, not these pages.
13. **URLs are not always guessable.** The 2019–20 season has
    `NBA_2020_games-october-2019.html` and `-october-2020.html`; month links
    must be read from the season page, not constructed. Postponed games that were
    never played are not listed.

## Cost of Stage 2

At the measured 6.1–6.3 seconds per request:

| Scope | Requests | Time | Cache |
|---|---:|---:|---:|
| Schedule months, 2014–15 to 2025–26 (about 9 per season) | ~108 | ~11 min | ~6 MB |
| Regular-season box scores, 2014–15 to 2025–26 (14,439 games) | ~14,440 | ~25 h | ~0.8 GB |
| Play-by-play for the same games (Stage 4) | ~14,440 | ~25 h | ~0.7 GB |

Game count: ten 1,230-game seasons plus 1,059 in 2019–20 and 1,080 in 2020–21.
The upcoming 2026–27 schedule is already published (88 games in its October
page), which the product needs for its forecasts.

## Running it again

From the repository root, with a real contact in the user agent for the process
(`.env` still holds the `.env.example` placeholder):

```powershell
$env:SCRAPER_USER_AGENT = "nba-data-project/0.1 (+https://github.com/alejandrou/NBA_ML-.)"
uv run nba-data acquisition dry-run-game-pilot tasks/manifests/F8-001-game-pilot-games-20260923.json
uv run nba-data acquisition acquire-game-pilot tasks/manifests/F8-001-game-pilot-games-20260923.json --owner-approved --execute-approved-manifest --output reports/f8-001/acquisition-games.json
uv run nba-data validate game-pilot --manifest tasks/manifests/F8-001-game-pilot-schedules-20260923.json --manifest tasks/manifests/F8-001-game-pilot-games-20260923.json --acquisition-report reports/f8-001/acquisition-schedules.json --acquisition-report reports/f8-001/acquisition-games.json --output reports/f8-001/validation.json
```

The acquire command needs the owner's direct instruction every time; with the
pages cached it makes no request. The validation reads only the cache. Reports
go under `reports/`, which is never committed.

## Tooling

- `scraping/game_pilot_manifest.py` — the approved-manifest contract: three page
  types, strict Basketball Reference URLs, the pace ceiling, and the owner's
  approval.
- `scraping/game_pilot_acquisition.py` — cache-first, sequential, stop-on-first-
  failure acquisition with per-page requests, bytes, and wall time.
- `scraping/parsers/league_schedule.py`, `box_score.py`, `play_by_play.py` —
  pure parsers, tested against trimmed real pages in `tests/fixtures/html/`.
- `validation/game_pilot.py` — the reconciliation behind
  `nba-data validate game-pilot`. It fails closed: no game named, a game's box
  score or linked play-by-play left out of the manifests, a blank value (never
  read as zero), or a malformed page each fail the report.
