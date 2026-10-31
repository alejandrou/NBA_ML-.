# Business Rules

## League and Seasons

- Initial scope is NBA only.
- Design may include a `league` dimension for future extension.
- `season_year = 2024` represents the 2023-24 season.
- Older seasons can have missing columns or statistics that did not exist.
- Missing because unavailable, not scraped, and parse error must be distinguished
  in future data quality work.

## Teams

- Real teams change name, city, abbreviation, and franchise affiliation over
  time. The rules below settle how that history is modeled.
- A `core.teams` row is a **code-era identity**: one row per Basketball Reference
  team code. `SEA` and `OKC` are two rows, as are `NJN` and `BRK`, and as are
  Charlotte's `CHH`, `CHA`, and `CHO`.
- The rule applies uniformly to all five code transitions the archive contains:
  `VAN` to `MEM`, `SEA` to `OKC`, `NJN` to `BRK`, `CHA` to `CHO` (a rename in
  place), and the `CHH` to `NOH` to `NOK` to `NOP` chain. New Orleans' codes are
  `NOH`, `NOK`, and `NOP`; none of them is Charlotte's.
- Aliases carry the per-row history. `core.team_aliases`, populated by the
  team-season loader, holds the name and abbreviation a team used over a range of
  seasons.
- **Franchise lineage across codes is unmodeled.** Nothing links `SEA` to `OKC`,
  `franchise_id` is never written by any loader, and neither the schema nor the
  v1 API promises that lineage will exist.
- `basketball_reference_team_id` is the public key for a team, and it is required
  on every row. See `docs/architecture/API_CONTRACT.md` for the served contract.
- Team aliases may have `from_season_year` and `to_season_year`.
- `TOT` and every multi-team marker are not real teams and must not be inserted
  into `core.teams` or `core.team_seasons`.

### Every team code resolves to exactly one name

All 775 cached team-season pages were parsed with the repository's own team-name
selector — `TEAM_NAME_SELECTOR`, `h1 > span:nth-of-type(2)`, in
`src/nba_data/scraping/parsers/team_season.py` — and the parsed name grouped by
the code in the cache filename. **37 distinct codes, zero parse failures, and
every code resolves to exactly one team name.** No code is reused by a different
club and no code changes name mid-archive, so a plain code-to-name map is correct
for every code present and **effective-dated franchise edges are not required.**

Two qualifications make the map safe to rely on:

- **A code's season set is not always an interval.** `NOH` covers 2003–2005 and
  2008–2013, interrupted by `NOK` for 2006–2007. It is the only such code, and it
  carries the same name across both runs, so this narrows nothing about the
  code-to-name result — but never infer a contiguous season range from a code.
- **The map runs from code to name and never the reverse.** `CHH` and `CHO` both
  render *Charlotte Hornets*, the one name in the archive carried by two codes,
  so a lookup by name is ambiguous for exactly this pair.

The measurement covers the 2000–2025 archive. Acquiring earlier seasons changes
the evidence base and reopens it.

### Charlotte has two lineages, and they disagree

The NBA separated Charlotte's organizational and statistical history on purpose:

- **Organizational continuity** — the 1988 Charlotte expansion franchise
  relocated to New Orleans in 2002 and is the legal entity that is today the
  Pelicans; the 2004 Bobcats were a new expansion franchise. This lineage runs
  `CHH` to `NOH` to `NOK` to `NOP`.
- **Official statistical history** — on the 2013 renaming the NBA assigned the
  1988–2002 Charlotte Hornets records to the Charlotte club, joined to the
  Bobcats' 2004–2014 history, so the New Orleans franchise's official history
  begins in 2002-03. This lineage runs `CHH` plus `CHA` to `CHO`.

Sources:
<https://www.nba.com/hornets/charlotte-hornets-name-returns-carolinas> and
<https://www.nba.com/pelicans/news/countdown-pelicans-training-camp-18-days>.

`VAN`/`MEM`, `SEA`/`OKC`, and `NJN`/`BRK` are ordinary relocations where the two
lineages agree. Charlotte is the one case in this archive where they diverge,
because the league moved the history without moving the entity. A single lineage
column can carry one of the two, so it would have to pick a side silently in the
one case where the choice is visible. The code-era rule asserts neither, which is
why it is the right shape here rather than a smaller answer; both lineages are
recorded above so later work starts from the distinction.

### `core.teams.franchise_id` stays, unwritten

`franchise_id` remains a nullable column on `core.teams`, created by migration
`0001` and written by nothing in `src/`. That is the standing disposition. The
column is kept because a real generator for it exists — curated lineage data —
and it stays empty and unserved because the archive asserts no lineage. It is
withdrawn from the v1 teams response; see `docs/architecture/API_CONTRACT.md`.
Reinstating it takes a card that names **which** of the two lineages above it
carries, states where the curated data comes from, and carries its own backfill
approval.

## Players

- A player is a global entity.
- A player can have multiple team stints in one season.
- Do not use `player_name` as a stable key.
- Use `basketball_reference_player_id` when available.
- `basketball_reference_player_id` is the public API key for a player as well as
  the internal stable identifier, and no other player identifier is published —
  not the surrogate `core.players.id`, and not a slug. See
  `docs/architecture/API_CONTRACT.md` for the served contract.
- If the legacy scraper does not extract player IDs yet, document that as debt.
- Basketball Reference renders current player names retroactively across the
  cached archive. No era-specific names were observed, so a displayed name is
  source text rather than historical identity and must not replace
  `basketball_reference_player_id`.

## Source Team Codes and Trades

- `TOT` is not a real team, and it is not a multi-team marker.
- A multi-team marker is a numeric team count of at least two followed by `TM`:
  `2TM`, `3TM`, `4TM`, `5TM`, and any higher count. `0TM`, `1TM`, and malformed
  forms such as `02TM` are not markers. The set is open-ended — the cached
  archive already contains a `5TM` season — so never enumerate it.
- Multi-team markers are official player-page source markers for multi-team
  full player-season rows.
- A multi-team marker may be **published** as source metadata on an aggregate
  row, but it is never a public team and never resolves to a team resource. The
  rule that governs storage governs publication too: consumers distinguish a
  marker from a team code by the semantic rule above, never by an enumerated set.
- The rule has one implementation, `src/nba_data/domain/team_codes.py`, and is
  enforced in the database by the four `ck_core_*_not_synthetic` check
  constraints as well as in code.
- Real team rows such as `BOS`, `HOU`, and `BRK` belong in team-season and
  player-team-season grains.
- Full player-season stats belong in `stats.player_season_*`.
- Team-stint stats belong in `stats.player_team_season_*`.
- Do not calculate full player-season stats by summing team stints or
  averaging percentages.
- Game Highs are not a supported source for official season stats.

## Postseason Stats

- Postseason stats must be stored in separate future `stats` tables.
- Do not mix postseason stats into regular-season `player_season_*` or
  `player_team_season_*` tables.

## Games and Box Scores

Stored in `core.games`, `stats.team_game_totals`, and `stats.player_game_totals`
(revision `0009_games_and_box_scores`). Sourced from Basketball Reference
schedule and box score pages (ADR 0020); evidence in
`docs/validation/PER_GAME_ACQUISITION_PILOT.md`.

Storage and database constraints:

- The game id is the Basketball Reference id, `<yyyymmdd>0<home code>`, stored
  as text with a unique constraint and a format check. The check validates
  the shape only; it does not compare the embedded date or code to other fields.
- A game's two teams differ and both belong to the game's season.
- `game_type` is one of `regular_season`, `play_in`, `playoffs`, `cup_final`, or
  NULL. The parser's `unknown` is never stored; a `final` game must have a type.
- Status is one of `scheduled`, `final`, or `postponed`.
- Attendance NULL means the page left it blank; 0 is a published zero. The two
  have distinct stored values; negative attendance is rejected.
- `neutral_site` NULL means not determined. It never defaults to false.
- The tip-off time is stored as published, US Eastern, beside the date; it is
  not converted to a timestamp.
- Each side and team has **at most** one team total per game, and each player
  at most one line. Uniqueness does not require either side's total to exist.
- Participation is one of `played`, `did_not_play`, `did_not_dress`,
  `not_with_team`, `suspended`, `other_absence`, `inactive`, with the published
  reason text stored separately when present.
- A `played` line has seconds, which may be 0. Any other line is not a starter
  and carries no seconds, no counting stat, and no plus-minus. A played line of
  zeros and a "Did Not Play" line are therefore always distinguishable.
- A played line's plus-minus may be NULL (a 0:00 line) or negative. Counters and
  seconds are never negative; a blank counter is NULL, not zero.
- A player line exists only for a team whose total for that game is loaded.

Loader responsibilities (F8-005 for completed games, F8-014 for the current
schedule), including cross-table checks and source handling:

- A `final` game has exactly two team totals, which are the game's own home and
  away teams with matching `is_home` flags and different points. The schema
  does not tie a team total's side or season to the game.
- Keep the published game id and confirm its date and home code agree with the
  schedule. Build a scheduled game's id by the same rule.
- A game that leaves its date is marked `postponed`, not deleted: Basketball
  Reference gives the rescheduled game a new id, and a stored forecast keeps its
  game. The status check alone does not enforce this transition policy.
- Keep each published participation reason and create lines for inactive
  players, so availability is retained.
- The schedule's score equals the box score's team points.
- The result comes from `stats.team_game_totals.pts`, the one place it is
  stored; never from a sum of player rows.
- A team's `tov` is its own total, team turnovers included (0–3 a game that no
  player carries), so it is not the sum of its player rows.
- Line scores are not stored yet; one game in 30 in the pilot had a wrong line
  score at the source, so reconciling them needs its own rule.
- Cup-final plus-minus that is all zeros is source noise and is stored as NULL.
- Neutral site is derived, not assumed.
- Players missing from `core.players` are created from box score links, by
  stable id and never by name. No team-season is invented from a box score.

### Loading finished games (F8-005)

`nba-data backfill games` (`scraping/offline_games_backfill.py`, loader
`scraping/loaders/games.py`) loads only finished games: a game the F8-004
selection keeps (regular season plus the NBA Cup final) whose box score is
cached, with `status = 'final'`. A selected game without a cached box score is
reported as missing coverage, never written. A game's season is the season of
the schedule page that lists it.

**Gates.** Every gate runs before any write; a game that fails one writes
nothing and is reported under every reason it fails. Each game is its own
transaction, so the other games still load.

| Reason | The game is quarantined when |
|---|---|
| `unknown_game_type` | the heading names no known type (regular season, play-in, playoffs, Cup final) |
| `missing_team_season` | either team has no `core.team_seasons` row in the game's season |
| `team_mismatch` | the box score's teams differ from the schedule's, or from the home code in the game id, or the scorebox names no two teams |
| `score_mismatch` | the schedule, the scorebox, and the team totals' `pts` do not all agree, or the schedule or scorebox score is blank |
| `tied_score` | the final score is tied |
| `missing_team_totals` | a team total has no `pts` or no minutes |
| `player_sum_mismatch` | a counter on the played lines does not sum to the team total, or is blank on a line or the total; `tov` may exceed the lines by the team's own turnovers, never fall short |
| `unknown_participation` | a line's participation is not one of the seven stored values, or an absence carries no reason text |
| `played_without_seconds` | a played line has no minutes |
| `duplicate_player` | a player is listed twice in one game (two lines, or a line and an inactive entry) |
| `unnamed_player` | a player missing from `core` has no link text to be created with |
| `unreadable_start_time` | the schedule's start time is neither blank nor `h:mm` + `a`/`p` |
| `box_score_unreadable` | the box score parser reported an issue no other gate judges, such as a player row without a player link |
| `game_id_mismatch` | the game id's date differs from the schedule date |
| `minutes_mismatch` | team minutes differ from the schedule's game length, or player seconds differ beyond half a second per played line |
| `invalid_box_score_values` | attendance, seconds, or a counting stat is negative |

These are the pilot's reconciliation rules (`validation/game_pilot.py`): the
`player_sum_mismatch` gate is the same function as the pilot's
`player_sums_match_totals` check.

**Warnings, not quarantines.** Line scores are not stored, so a line score that
is unreadable, whose total differs from the final score, whose periods do not
sum to its total, whose period count differs from 4 plus the schedule's
overtimes, or whose period points differ from published quarter/overtime box
totals is reported as a warning and the game loads. Those optional boxes are
checked when present; missing quarter boxes do not require acquisition. A final-score
disagreement is a quarantine. A play-in or playoff heading on a selected game is
loaded with that `game_type` and listed in the report for review.

**Stored values.** `start_time_et` is the schedule's time read as US Eastern
("7:30p" → 19:30); blank is NULL. Attendance and venue come from the box score
as published: blank attendance is NULL and 0 is 0. `participation_reason` is the
published reason; inactive entries store `inactive` with reason `Inactive` and,
like every absence, no starter flag, seconds, counters, or plus-minus. A rerun
over the same pages assigns no column and reports the game `unchanged`; a line
the page no longer lists is deleted.

**Cup-final plus-minus.** When every played line of a `cup_final` game carries
plus-minus 0, every line stores NULL (the 2023 final). A Cup final with real
values keeps them; a regular-season line of 0 keeps its 0.

**Neutral site.** A second pass over the whole loaded season sets only
`neutral_site`. The venue city is the text after the venue's first comma
("Accor Arena, Paris, France" → "Paris, France"). A game is neutral when its
city differs from the most common city of its home team's home games that
season. This marks the London, Paris, Mexico City, and Tokyo games, the Las
Vegas Cup games, and the 2020 bubble, while an arena rename in the same city
(Staples Center → Crypto.com Arena) and two teams sharing a city stay at home.
No venue, or no single most common home city, leaves `neutral_site` NULL
(undetermined). It is a rule over the published venues, not a curated list:
each season's neutral games are listed in the report for review.
The backfill defers this pass until all selected games are present in the
database, except games quarantined as source errors in the same run. A run
with a missing box score or a failed load in the season reports
`neutral_site_deferred` and changes no flags — even when an earlier run stored
that game — so an isolated cached game abroad cannot establish a team's home
city.

**Created players.** A player with a box score line or inactive entry who is
missing from `core.players` is created with the id and link text of the box
score link and no `core.player_seasons` row. The API's player list therefore
shows such a player with no seasons, which is accurate: the archive holds no
season page for them. An existing player is never renamed from a box score.

**Lineage.** `stats.team_game_totals` and `stats.player_game_totals` carry the
box score URL, its cache path, and the `box_score` parser contract
(`validation/parser_contracts.py`); `core.games` has no lineage columns.

## Official Stats and Generated Metrics

- Official scraped data remains separate from project-generated metrics.
- Generated metrics belong in the `features` schema.
- Formula versions must be recorded for generated metrics.
- Future ML features must avoid data leakage.
