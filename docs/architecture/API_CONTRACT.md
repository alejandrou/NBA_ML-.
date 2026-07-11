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

## Planned resources

The following are planned, not implemented:

- `GET /api/v1/teams`
- `GET /api/v1/teams/{team_id}`
- `GET /api/v1/seasons`
- `GET /api/v1/seasons/{season_year}`
