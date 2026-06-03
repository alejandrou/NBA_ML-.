# F4E-005 - Offline Stats Backfill Command

## Goal

Add a guarded offline command that loads official wide stats from existing
cached team-season HTML through the approved parse, normalize, validate, core,
and stats loader chain.

## Requirements

- Run only against already-cached inventory entries.
- Reuse the existing offline processor and reporting patterns.
- Ensure core identity loading has completed or runs in the same guarded
  offline flow before stats loading.
- Load stats only from validated normalized rows.
- Use entry-level transaction boundaries so one failed entry does not leave
  partial stats writes.
- Require an explicit execution flag such as
  `--execute-approved-stats-backfill`.
- Support JSON report output if it fits the existing CLI/reporting pattern.
- Do not scrape, refresh cache misses, contact Basketball Reference, delete
  data, or run destructive migrations.

## Acceptance Criteria

- Command refuses to write stats without the explicit execution flag.
- Backfill selects only valid cached inventory entries.
- Backfill loads no stats for processor failure entries.
- Backfill reports loaded, skipped, failed, and quarantined stats rows.
- Rerunning the same backfill does not duplicate stats rows.
- Tests cover CLI guard behavior, no-network boundaries, idempotency,
  partial-failure reporting, and transaction rollback.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference contact.
- Cache refresh or cache-miss acquisition.
- Data deletion, DB reset, or destructive migrations.
- API, frontend, generated metrics, OVR, ranking, similarity, or ML work.

