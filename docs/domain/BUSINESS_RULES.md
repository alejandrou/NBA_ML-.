# Business Rules

## League and Seasons

- Initial scope is NBA only.
- Design may include a `league` dimension for future extension.
- `season_year = 2024` represents the 2023-24 season.
- Older seasons can have missing columns or statistics that did not exist.
- Missing because unavailable, not scraped, and parse error must be distinguished
  in future data quality work.

## Teams

- Teams can change name, city, abbreviation, and franchise history.
- Future modeling should separate franchise, team, and aliases.
- Team aliases may have `from_season_year` and `to_season_year`.
- `TOT`, `2TM`, `3TM`, and `4TM` are not real teams and must not be inserted
  into `core.teams` or `core.team_seasons`.

## Players

- A player is a global entity.
- A player can have multiple team stints in one season.
- Do not use `player_name` as a stable key.
- Use `basketball_reference_player_id` when available.
- If the legacy scraper does not extract player IDs yet, document that as debt.

## Source Team Codes and Trades

- `TOT` is not a real team.
- `2TM`, `3TM`, and `4TM` are official player-page source markers for
  multi-team full player-season rows.
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
