# Next Decisions

Defaults are recorded here until the owner chooses otherwise.

## Defaults

- Initial scope is NBA only.
- Development is local first.
- No public API for now.
- Raw HTML storage is local `.html.gz`.
- Future raw HTML object storage may be S3 or R2, but is not implemented now.
- Legacy scraper consolidation must happen before controlled raw HTML backfill.
- Live Basketball Reference acquisition stays sequential/cache-first by
  default; offline cached HTML processing may use bounded parallelism only in a
  later approved task.

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
