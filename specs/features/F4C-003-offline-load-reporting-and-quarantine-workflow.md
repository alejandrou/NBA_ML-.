# F4C-003 - Offline Load Reporting and Quarantine Workflow

## Goal

Add an auditable reporting layer for Phase 4C offline processing and loading.
The report must make successful rows, skipped work, failures, and quarantined
rows visible without contacting Basketball Reference or refreshing cache
misses.

The reporting boundary is:

```text
OfflineTeamSeasonProcessingReport + OfflineTeamSeasonLoadReport -> audit report
```

This task does not add database tables, migrations, persisted lineage columns,
API endpoints, frontend pages, generated metrics, or a full historical load.

## Functional Requirements

- Reports distinguish parsed, validated, loaded, skipped, and quarantined row
  counts.
- Validation failures keep invalid normalized rows out of loader input while
  preserving them as quarantined rows in the report.
- Loader failures quarantine the validated rows for that failed entry and keep
  successful entry loads separate.
- Quarantine entries include source context needed for a retry:
  `source_url`, `cache_path`, `team_abbreviation`, and `season_year`.
- Validation failures include validation issue details so parser or normalizer
  fixes are actionable.
- Reports must be retry-safe: rerunning the same validated input through the
  idempotent loaders must not silently create duplicate rows.
- Reporting works from existing report objects only and must not accept a
  network client or refresh cache misses.

## Operator Flow

1. Run the offline processor against already-cached `.html.gz` sources.
2. Load only validated processor entries through the offline loader bridge.
3. Build the audit/quarantine report from the processing and load reports.
4. For validation quarantines, fix the parser, normalizer, source metadata, or
   cached HTML fixture, then rerun the offline processor and loader.
5. For loading quarantines, fix the loader input or database-side issue, then
   rerun the same validated report through the idempotent loader path.
6. Confirm the next audit report has fewer quarantined rows and no unexpected
   duplicate load effects.

## Acceptance Criteria

- Feature spec exists at
  `specs/features/F4C-003-offline-load-reporting-and-quarantine-workflow.md`.
- Reports distinguish parsed, validated, loaded, skipped, and quarantined rows.
- Failures include enough source context to rerun or fix parser/normalizer
  issues.
- Partial failures do not silently create duplicates on retry.
- Reporting works without live scraping or cache refresh.
- Docs explain the operator flow for retrying after fixes.

## Validation

- `python -m json.tool tasks/feature-list.json`
- `uv run ruff check .`
- `uv run pytest`
- `C:\Program Files\Git\bin\bash.exe scripts/harness/validate.sh`

## Out Of Scope

- Live scraping or Basketball Reference contact.
- Cache refreshes or cache-miss acquisition.
- SQLAlchemy migrations, new DB tables, lineage columns, destructive DB
  changes, or data deletion.
- Raw HTML deletion, database record deletion, volume deletion, Peewee deletion,
  or legacy code deletion.
- Full historical load.
- API, frontend, generated metrics, OVR, ranking, similarity, or ML work.
