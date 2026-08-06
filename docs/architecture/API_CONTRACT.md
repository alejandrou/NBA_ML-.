# API contract

## Version

All public routes use `/api/v1`.

## Content type and naming

Responses use `application/json`. JSON fields use stable `snake_case` names within v1. A single resource is an explicit Pydantic-defined JSON object; ORM models are never the public contract.

## Collection response

```json
{
  "items": [],
  "page": 1,
  "page_size": 50,
  "total": 0
}
```

`page` defaults to 1 and is at least 1. `page_size` defaults to 50, is at least 1, and is at most 100. `total` counts filtered records before pagination. Ordering is deterministic. A valid page with no results returns 200 and an empty `items` list.

## Errors

FastAPI/Pydantic path and query validation returns 422. A missing resource returns 404. Input that is syntactically valid but semantically incompatible returns 400. Unexpected failures return 500. Error bodies use the standard `detail` field and never expose SQL, credentials, local paths, or other internals.

## Health

`GET /api/v1/health` returns:

```json
{
  "status": "ok"
}
```

It is liveness only: it does not verify the database, scraping, or external services.

## Teams

`GET /api/v1/teams` returns the paginated collection. `GET /api/v1/teams/{team_id}` returns one team, or 404 when the identifier is unknown. `team_id` is the internal `core.teams` identifier and is the public key for this resource.

```json
{
  "team_id": 7,
  "basketball_reference_team_id": "ATL",
  "current_abbreviation": "ATL",
  "current_name": "Atlanta Hawks",
  "franchise_id": "hawks"
}
```

`basketball_reference_team_id`, `current_abbreviation`, and `franchise_id` are nullable. Ordering is `current_name ASC, team_id ASC`.

## Seasons

`GET /api/v1/seasons` returns the paginated collection. `GET /api/v1/seasons/{season_year}` returns one season, or 404 when the year is unknown.

```json
{
  "season_year": 2024,
  "league": "NBA",
  "label": "2024"
}
```

`season_year` is the public identifier: `2024` means the 2023-24 season. The internal `core.seasons` identifier is never exposed. `label` is the stored display label for the season; the current loader writes the season year as a string, so it repeats `season_year`. The column is nullable, so clients must tolerate `null` and must not parse `label` for meaning. Ordering is `season_year DESC, league ASC`.

### Season identity

`core.seasons` is unique on `(league, season_year)`, so `season_year` alone is only a valid key inside a fixed league. **v1 fixes that league to NBA permanently.** Both routes read `league = "NBA"`: `total` counts NBA seasons, and a year that exists only in another league returns 404. `/api/v1/seasons/2024` therefore means "the NBA 2024 season" for the life of v1 and will never be redefined to mean another league's 2024 season.

Any resource that references a season — teams by season, player seasons, statistics — inherits this scope and must not reintroduce league as a path or query dimension within v1. If another league is ever published, it gets its own resource; it does not reshape this one. A `league` filter may be added later as an additive, non-breaking query parameter, but the NBA default cannot change.

The `league` field stays in the response so the scope is explicit in every payload rather than implied by the URL.
