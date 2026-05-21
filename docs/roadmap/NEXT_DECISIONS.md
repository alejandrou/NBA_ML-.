# Next Decisions

Defaults are recorded here until the owner chooses otherwise.

## Defaults

- Initial scope is NBA only.
- Development is local first.
- No public API for now.
- Raw HTML storage is local `.html.gz`.
- Future raw HTML object storage may be S3 or R2, but is not implemented now.
- Legacy scraper consolidation must happen before controlled raw HTML backfill.
- Legacy parser/refactor correctness is validated offline from frozen or cached
  HTML fixtures.
- Live Basketball Reference acquisition stays sequential/cache-first by
  default; offline cached HTML processing may use bounded parallelism only in a
  later approved task.
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
- Controlled raw HTML backfill manifest scope and approval process.
- Offline cached HTML processing concurrency model.
- Final branch and PR strategy.
