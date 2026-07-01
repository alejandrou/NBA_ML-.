# Project Spec

## A. Contract

- Source site: Basketball Reference, part of Sports Reference.
- Default live request limit: 10 requests/minute.
- Absolute maximum: 20 requests/minute.
- Minimum default delay: 6 seconds.
- Cache policy: use local `.html.gz` raw HTML cache by default.
- Database: PostgreSQL.
- New ORM: SQLAlchemy 2.0.
- Migrations: Alembic.
- Initial schemas: `raw`, `core`; future schemas: `stats`, `features`, `ml`, `app`.
- Package manager: `uv`.
- Tests and CI must not call Basketball Reference.

## B. Domain

- Initial league: NBA.
- `season_year` stores the ending year of a season.
- Players and teams should use Basketball Reference identifiers when available.
- Team aliases capture name and abbreviation changes.
- Roster stints represent player-team-season membership.
- `TOT`, `2TM`, `3TM`, and `4TM` are not teams.
- `2TM`, `3TM`, and `4TM` may appear as official player-page source markers.
- Historical seasons may have unavailable metrics.

## C. Validation

- Unit tests cover settings, cache, client, and parser behavior.
- Parser tests use fixture HTML.
- Client tests use mocks and do not contact the network.
- Future DB integration tests should be isolated and explicitly marked.
- Live tests are manual only and skipped by default.
- Loaders must be idempotent.
