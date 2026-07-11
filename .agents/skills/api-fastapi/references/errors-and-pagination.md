# API reference: errors and pagination

FastAPI/Pydantic validation remains 422. Return 404 for a missing resource, 400 for syntactically valid but semantically incompatible filters, and 500 for unexpected failures. Do not expose SQL exceptions or replace the default validation handler without an explicit contract decision; stable contract messages use `detail`.

Collections expose `items`, `page`, `page_size`, and `total`. `page` defaults to 1 and has minimum 1. `page_size` defaults to 50, has minimum 1, and maximum 100. Count after filters and before pagination. Apply typed filters and deterministic `ORDER BY` with a primary-key or equivalent stable tie-breaker. Never paginate unordered results. Valid pages beyond the last result return 200 with `items: []`.

```text
GET /teams?page=0 -> 422
GET /teams?page=999 -> 200 with items=[]
GET /teams/unknown -> 404
GET /teams?from_year=2025&to_year=2020 -> 400
```

Do not declare filters not approved in the API contract.
