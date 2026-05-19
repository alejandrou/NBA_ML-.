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

## Players

- A player is a global entity.
- A player can have multiple team stints in one season.
- Do not use `player_name` as a stable key.
- Use `basketball_reference_player_id` when available.
- If the legacy scraper does not extract player IDs yet, document that as debt.

## TOT and Trades

- `TOT` is not a real team.
- `TOT` represents an official player-season aggregate for a player who appeared
  for multiple teams in the same season.
- Future target tables should separate player-season totals from
  player-team-season totals.

## Official Stats and Generated Metrics

- Official scraped data remains separate from project-generated metrics.
- Generated metrics belong in the `features` schema.
- Formula versions must be recorded for generated metrics.
- Future ML features must avoid data leakage.
