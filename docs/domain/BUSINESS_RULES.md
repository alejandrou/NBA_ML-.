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

## Official Stats and Generated Metrics

- Official scraped data remains separate from project-generated metrics.
- Generated metrics belong in the `features` schema.
- Formula versions must be recorded for generated metrics.
- Future ML features must avoid data leakage.
