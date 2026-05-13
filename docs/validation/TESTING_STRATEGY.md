# Testing Strategy

## Phase 1 Tests

- Unit tests for settings defaults.
- Unit tests for HTML cache `.html.gz` read/write behavior.
- Unit tests for the rate-limited client with mocked HTTP.
- Unit tests for parser behavior with fixture HTML.

## Rules

- No network calls in tests.
- No live scraping in CI.
- No Basketball Reference contact in CI.
- Use fixture HTML for parser tests.
- Use mocks for HTTP client tests.
- Use temporary directories for cache tests.

## Future Tests

- DB integration tests for SQLAlchemy models and repositories.
- Data quality tests for row counts, nullability, duplicate natural keys, and
  numeric ranges.
- Manual live smoke tests for approved scraping jobs only.
