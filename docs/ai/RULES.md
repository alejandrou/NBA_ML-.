# AI Project Rules

These rules apply to all generated code, docs, tests, and reviews.

## Code Generation Rules

- Do not hardcode secrets, credentials, tokens, or database passwords.
- Do not run live scraping in tests or CI.
- Do not make HTTP requests outside the central rate-limited client.
- Do not add new Peewee code.
- Do not use `create_tables()` as the new schema mechanism.
- Do not add a new dependency without a clear reason.
- Do not perform giant refactors.
- Do not mark a task as done without validation.

## Scraping Rules

- Check HTML cache before requesting a page.
- Save raw HTML as compressed `.html.gz`.
- Respect 10 requests/minute by default.
- Never exceed 20 requests/minute.
- Respect `Retry-After`.
- Back off on HTTP 429.
- Stop the job on repeated HTTP 429.
- Do not use rotating proxies, bypasses, or evasion.

## Parser Rules

- Parsers receive HTML and return structured data.
- Parsers must not make network requests.
- Parsers must not touch the database.
- Parsers should support Basketball Reference tables hidden inside HTML comments.
- Normalization and loading are separate responsibilities.

## Database Rules

- New persistence code uses SQLAlchemy 2.0.
- Schema changes use Alembic.
- Use schemas: `raw`, `core`, `stats`, `features`, `ml`, `app`.
- Use unique constraints for idempotency.
- Use foreign keys and indexes for common lookups.
- Do not delete data without explicit owner approval.

## Domain Rules

- Initial scope is NBA only.
- `TOT` is a player-season aggregate, not a real team.
- Do not use names as stable keys.
- Prefer Basketball Reference IDs when available.
- Official scraped stats belong in `stats`.
- Generated metrics belong in `features`.
- Future ML features must avoid data leakage.
