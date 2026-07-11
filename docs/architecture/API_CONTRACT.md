# API contract

## Version and responses

The planned public prefix is `/api/v1`. Single resources return a JSON object;
collections return `{ "items": [], "page": 1, "page_size": 50, "total": 0 }`.
Implementations must use explicit Pydantic response schemas.

Errors use FastAPI's HTTP error shape with a stable `detail` value and an
appropriate status code. Validation errors remain distinguishable from missing
resources and server errors.

Collection filters and pagination are typed, bounded, and documented. Clients
may rely on response field names within `/api/v1`; breaking changes require a
new version or an explicit compatibility decision.

## Planned endpoints

- `GET /api/v1/health` — planned foundation health check.
- `GET /api/v1/teams` — planned read-only team collection.
- `GET /api/v1/seasons` — planned read-only season collection.

These endpoints do not exist until their task cards are approved and
implemented.
