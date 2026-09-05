---
id: F4E-031
title: Apply the rehearsed -v4 player-page rebuild to the persistent nba database
areas:
  - data-quality
  - database-schema
priority: 52
depends_on:
  - F4E-024
  - F4E-029
  - F4E-030
read:
  - docs/validation/OFFLINE_DATABASE_PREPARATION.md
  - docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md
  - scripts/dev/rehearse_player_page_rebuild.py
validation:
  - uv run nba-data validate offline-database --backfill-report reports/offline_backfill.json
  - uv run nba-data validate official-stats --team-stats-report reports/stats_backfill.json --player-stats-report reports/player_stats_backfill.json --player-postseason-stats-report reports/player_postseason_stats_backfill.json --coverage-artifact reports/stats-coverage.json
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Apply migration 0007_team_bref_id_not_null to the persistent nba database
  - Run backfill offline, backfill stats, backfill player-stats and backfill player-postseason-stats against the persistent nba database
  - Overwrite persisted stats rows in nba with -v4 player-page lineage
---

# Goal

Repair the real data. `F4E-024` proved the `-v4` rebuild recovers 625 lost
regular-season player-seasons and 235 postseason player-seasons with **zero**
rows lost — but it proved it on a scratch database that was dropped. The
persistent `nba` database still carries the `-v1` archive, still one migration
behind head, and `DB-02` in the archive audit is still an open data defect.

# Evidence and current state

`docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md` records `DB-02` as "fixed at
the parser; repair rehearsed and measured, not yet applied to `nba`". The parser
fixes landed in `F4E-014` and `F4E-022`; the lineage contract landed in
`F4E-025`; `F4E-024` measured the repair end to end and wrote the handover
procedure. Nothing has touched `nba`.

What the rehearsal measured on scratch database `nba_f4e024_tmp_1ea6e5ff607b4184`
(2026-08-28), reproduced across two runs:

| Grain | `-v1` (today's `nba`) | `-v4` rebuild |
|---|---|---|
| Distinct regular-season player-seasons | 12,042 | **12,667** (+625) |
| Distinct postseason player-seasons | 5,066 | **5,301** (+235) |
| Distinct postseason team stints | 5,066 | **5,301** (+235) |
| Team-season stints | 14,332 | 14,332 (unchanged) |
| Total rows across 33 `stats` tables | 306,392 | **315,152** |

- Bucket reconciliation: season 2000 **439**, short player ids **184**,
  `jonesbo02` 2008 **1**, `milleol01` 2004 **1** = **625**, with **0
  unclassified** and **0 lost**.
- `backfill player-stats` reported **0** failed entries, down from the 577 the
  archive audit recorded.
- `coverage_unexpected_<dimension>_row` was **0** in all four dimensions, so the
  upsert-only write path strands nothing and **no delete step is needed**.
- `parser_lineage_violations` **0**; exactly three parser versions persist.

`nba` is at `0006_synthetic_team_codes`; head is `0007_team_bref_id_not_null`.

The two blockers `F4E-024` recorded are what `F4E-029` and `F4E-030` remove: the
coverage oracle expects pre-2000 rows the archive never loads, and both producers
exit 1 on a complete run. Until those land there is no clean acceptance signal to
run this against, which is exactly why this card must not start early.

# Human decisions or resources

- [x] Whether to repair `nba` in place rather than rebuild from scratch —
  settled by measurement, not preference: `coverage_unexpected_*` came back 0 in
  all four dimensions and the before/after key diff found 0 lost, so the
  upsert-only path is sufficient and no destructive step is required.
- [x] Whether a backup is required before the run — yes, and it is step 1 of the
  procedure below. It is cheap and this is the only card in the family that
  writes to real data.
- [x] Whether this card authorizes its own critical actions — it does not.
  Listing them in `critical_actions` records that they are coming; running them
  needs the owner's direct, current instruction at execution time.

# Acceptance criteria

- A restorable dump of `nba` exists, taken immediately before any write, and its
  path is recorded in `# Review evidence

Applied to `nba` on **2026-09-05** under the owner's direct instruction, after a
full scratch-database rehearsal at head confirmed both validators exit 0.

**Restore point:** `reports/F4E-031/nba_pre_F4E-031_20260905T134035Z.dump`
(`pg_dump -Fc`, 18 MB, 394 TOC entries, verified readable with `pg_restore -l`),
taken immediately before `alembic upgrade head` and before any write.

**Before-baseline**, captured with `reports/F4E-024/lineage_census.sql`:
`reports/F4E-031/nba_lineage_before.txt`, `nba_grain_before.txt`,
`nba_regular_grain_before.txt`. `alembic_version` was
`0006_synthetic_team_codes`. The grain-key snapshot is byte-identical to the
F4E-024 baseline. `reports/F4E-024/` was copied to
`reports/F4E-024.pre-F4E-031/` first, because the rehearsal driver writes into
that directory.

## Automated validation

- Command: `uv run python scripts/dev/rehearse_player_page_rebuild.py`
- Result: **exit 0**. All 8 steps exit 0 on scratch database
  `nba_f4e024_tmp_5f55dfb5680c4fe7`, including both validators — the first
  end-to-end confirmation post-F4E-029/F4E-030. 12,667 / 5,301 / 5,301 / 14,332;
  625 recovered, 0 lost, 0 unclassified. Log: `reports/F4E-031/rehearsal.log`.

- Command: `uv run nba-data validate build-stats-coverage --output reports/stats-coverage.json`
- Result: **exit 0**. 16,840 entries, 0 unexplained, 0 disagreements, 0 source
  issues.

- Command: `uv run alembic upgrade head && uv run alembic check && uv run alembic current`
- Result: **exit 0**. `0006_synthetic_team_codes -> 0007_team_bref_id_not_null`;
  `alembic check` reports "No new upgrade operations detected"; `alembic current`
  reports `0007_team_bref_id_not_null (head)`.

- Command: the four producers against `nba`, in documented order
  (`backfill offline`, `backfill stats`, `backfill player-stats`,
  `backfill player-postseason-stats`), each with its approval flag, chained so a
  nonzero exit stops the run.
- Result: **all four exit 0**, 88 min end to end. `entries_failed` 0 and
  `rows_failed` 0 everywhere; `stats_loaded_rows` 129,000;
  `rows_loaded_or_updated` 101,336; postseason 42,408 aggregate + 42,408 team;
  `unresolved_*` 0 in both player producers; out-of-scope 19,692 and 20,280 —
  exactly the documented figures. Log: `reports/F4E-031/producers.log`.

- Command: `uv run nba-data validate offline-database --backfill-report reports/offline_backfill.json`
- Result: **exit 0**, `"issues": []`.

- Command: `uv run nba-data validate official-stats --team-stats-report reports/stats_backfill.json --player-stats-report reports/player_stats_backfill.json --player-postseason-stats-report reports/player_postseason_stats_backfill.json --coverage-artifact reports/stats-coverage.json --coverage-cache-root data/raw/html`
- Result: **exit 0**, `"issues": []`, `parser_lineage_violations` 0,
  `freshness_status` `verified`, `unexplained_count` 0, `source_issues_count` 0.
  All four dimensions **0 missing, 0 unexpected**: `regular_aggregate`
  101,336 / 101,336; `postseason_aggregate` 42,408 / 42,408;
  `regular_team_stint` 129,000 / 129,000; `postseason_team_stint`
  42,408 / 42,408.

- Command: `uv run python scripts/validate_tasks.py`
- Result: see below.

## Manual happy path

1. Re-run the before/after census on `nba` with
   `docker exec -i nba_postgres psql -U nba -d nba < reports/F4E-024/lineage_census.sql`
   and diff it against `reports/F4E-031/nba_lineage_before.txt`.
2. Diff `reports/F4E-031/nba_regular_grain_before.txt` against
   `nba_regular_grain_after.txt` and decompose the recovered keys into the four
   audit buckets.
3. Run the spot checks in `reports/F4E-031/nba_spot_checks.txt` against `nba`.

Expected result: the census returns exactly three parser versions —
`team-season-parser-v1`, `player-page-parser-v4`,
`player-page-postseason-parser-v4` — with **zero** rows carrying `-v1`, `-v2` or
`-v3` player-page lineage (observed). Grain counts **12,667 / 5,301 / 5,301 /
14,332** and **315,152** total rows across the 33 `stats` tables, up from
306,392 (observed, matching the rehearsal in every figure). The key diff shows
**625 recovered, 0 lost, 0 unclassified**, decomposing as season 2000 **439**,
short player ids **184**, `jonesbo02` 2008 **1**, `milleol01` 2004 **1**
(observed). Spot checks: `jonesbo02` 2008 has **8** regular-season aggregate
rows; `milleol01` 2004 has **8**, with `g = 48` and `pts = 121`; each of the 9
postseason-only seasons has **0** regular and **8** postseason aggregate rows
(all observed).

## Manual sad path

1. Point the rehearsal driver at the real database — set `DATABASE_URL` to the
   configured `nba` URL and run
   `uv run python scripts/dev/rehearse_player_page_rebuild.py`.
2. Truncate a handful of rows from one `stats.*` table on a scratch copy and
   re-run `validate official-stats` with the coverage artifact.
3. Edit or add a file under `data/raw/html` and re-run `validate official-stats`
   with `--coverage-cache-root`.

Expected result: (1) the driver refuses — its isolation guard rejects any
database outside the `nba_f4e024_tmp_` prefix and will not drop or target the
configured database; it is a safety interlock and was not bypassed for this
card. (2) the validator exits 1 and names the absent natural keys as
`coverage_missing_<dimension>_row` rather than reconciling on totals alone.
(3) the validator exits 1 with `coverage_artifact_stale` and skips key
comparison rather than trusting a fingerprint that no longer matches the cache.

## Known limitations

- The rebuild is upsert-only. It cannot remove a row the current parser no
  longer produces; the run's `coverage_unexpected_*` of 0 in all four dimensions
  is the evidence that no such row exists today, and no delete step was added.
- `reports/F4E-031/` (baselines, logs, and the `pg_dump` restore point) is
  gitignored and local to this machine. Nothing in it is committed.
- `docs/validation/OFFLINE_DATABASE_PREPARATION.md` still names
  `0002_core_team_player_season` as "the expected Phase 4D core database
  revision" in its early *Apply Migrations* section. That line was already stale
  before this card, describes Phase 4D rather than the archive rebuild, and was
  left alone rather than widened into this card's scope.
