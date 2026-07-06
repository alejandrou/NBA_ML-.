# Next Decisions

Defaults are recorded here until the owner chooses otherwise.

## Defaults

- Initial scope is NBA only.
- Development is local first.
- No public API for now.
- Raw HTML storage is local `.html.gz`.
- Future raw HTML object storage may be S3 or R2, but is not implemented now.
- Legacy scraper consolidation must happen before controlled raw HTML backfill.
- The roadmap order after Phase 4A is Phase 4B raw HTML backfill, Phase 4
  SQLAlchemy/loaders, Phase 4C offline cached HTML processing and load, then
  Phase 5 API.
- Phase 4B is acquisition only:
  `approved manifest -> BasketballReferenceClient -> HtmlCache -> .html.gz`.
- The first real controlled raw HTML backfill pilot defaults to at most five
  team-season URLs.
- Player-specific Basketball Reference pages are future scope; current player
  rows come from team-season pages unless a later manifest explicitly adds
  player-page acquisition.
- Phase 4E player-page stats implementation starts from fixtures and cached
  HTML only. Any live player-page acquisition requires exact owner approval for
  the player-page manifest before contacting Basketball Reference.
- Phase 4C first processes cached HTML offline, then loads only validated
  normalized rows through idempotent loaders. It is not direct DB loading from
  raw HTML.
- Legacy parser/refactor correctness is validated offline from frozen or cached
  HTML fixtures.
- Live Basketball Reference acquisition stays sequential/cache-first by
  default; offline cached HTML processing may use bounded local parallelism only
  under the Phase 4C design.
- Manual live acquisition smoke tests require owner approval for the exact
  Basketball Reference URL, team, and year.
- Manual live acquisition smoke tests default to `max_live_requests=1`.
- Manual live acquisition smoke tests validate acquisition/cache/parser shape,
  not exact long-term statistical equality against the live page.

## Future Owner Decisions

- Exact historical season start and end.
- Whether ABA should ever be included.
- Future deployment target.
- First OVR formula.
- Public or private API posture.
- Long-term raw HTML storage.
- Final historical backfill start and end seasons.
- Whether player-specific Basketball Reference pages should be included in a
  later acquisition manifest.
- Exact player-page acquisition/cache manifest for `F4E-007`, including the
  approved sample players and URLs.
- Final branch and PR strategy.
