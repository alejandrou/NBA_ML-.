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
  team code. `SEA` and `OKC` are two rows, as are `NJN` and `BRK`, and `CHH`,
  `NOH`, and `NOP`.
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

## Players

- A player is a global entity.
- A player can have multiple team stints in one season.
- Do not use `player_name` as a stable key.
- Use `basketball_reference_player_id` when available.
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
