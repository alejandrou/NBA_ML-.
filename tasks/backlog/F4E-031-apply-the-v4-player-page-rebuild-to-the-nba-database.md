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
  path is recorded in `# Review evidence`.
- The parser-version census across all 33 `stats` tables and the `alembic_version`
  row are captured **before** the run using
  `reports/F4E-024/lineage_census.sql`, and kept for the after-comparison.
- `alembic upgrade head` brings `nba` to `0007_team_bref_id_not_null`, and
  `alembic check` afterwards reports no new upgrade operations.
- All four producers run against `nba` and **exit 0** — this is only possible
  once `F4E-030` has landed, and a nonzero exit stops the run rather than being
  interpreted.
- `validate offline-database` exits 0.
- `validate official-stats` exits 0 with **zero** `coverage_missing_*` and
  **zero** `coverage_unexpected_*` findings in all four dimensions — only
  possible once `F4E-029` has landed.
- The after-census on `nba` shows exactly three parser versions —
  `team-season-parser-v1`, `player-page-parser-v4`,
  `player-page-postseason-parser-v4` — and **zero** rows carrying `-v1`, `-v2` or
  `-v3` player-page lineage. `parser_lineage_violations` is 0.
- The measured grain counts on `nba` match the rehearsal exactly: 12,667 /
  5,301 / 5,301 / 14,332, and 315,152 total rows. A deviation in any figure stops
  the card and is reported rather than accepted.
- Spot checks pass on `nba`: `jonesbo02` 2008 has 8 regular-season aggregate
  rows; `milleol01` 2004 has 8 with `g = 48` and `pts = 121`; each of the 9
  postseason-only seasons has 0 regular and 8 postseason aggregate rows.
- `ARCHIVE_DATA_AUDIT_DISPOSITION.md` records `DB-02` as repaired in `nba`, with
  the date and the measured after-figures.

# Scope

Data and schema state in the persistent `nba` database, and the two validation
documents that describe it. Running existing commands — nothing more.

# Out of scope

**All application code.** If this card finds itself editing `src/`, something is
wrong upstream: stop, and re-scope into `F4E-029`, `F4E-030`, or a new card. Live
scraping or any network access — the rebuild is cache-first and reads only cached
HTML already on disk. Changing the archive's season range. Any delete or
truncate against `stats` tables: the rehearsal proved none is needed, and adding
one on speculation is explicitly forbidden.

# Impact

Every `stats.*` table in `nba` (roughly +8,760 rows), `alembic_version`, and the
parser-version lineage of every player-page row. `validate offline-database` and
`validate official-stats` outputs. `ARCHIVE_DATA_AUDIT_DISPOSITION.md` and
`OFFLINE_DATABASE_PREPARATION.md`. No API surface, no schema design change beyond
applying an existing migration, no test change.

# Implementation notes

Follow the "Handover: running the rebuild against the persistent `nba` database"
procedure in `docs/validation/OFFLINE_DATABASE_PREPARATION.md`, which was written
from the rehearsal and carries the five numbered preflight steps and the
acceptance shape. Do not improvise an ordering: the producers must run in the
documented order, because the player-page producers resolve against rows the
earlier stages create.

`scripts/dev/rehearse_player_page_rebuild.py` is the rehearsal driver and points
a **child process** at a scratch database via `DATABASE_URL`. It must not be
repurposed to target `nba` — its isolation guard refuses names outside the
`nba_f4e024_tmp_` prefix, and that guard is a safety interlock, not an
inconvenience. Run the documented commands directly instead.

Budget roughly 70 minutes for the producers. Do not run this against `nba` while
anything else is reading it.

Re-run the rehearsal on a scratch database first, after `F4E-029` and `F4E-030`
have landed, to confirm both validators exit 0 there before writing to real data.

# Durable knowledge updates

- `docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md` — `DB-02` becomes repaired
  in `nba`, dated, with the after-figures.
- `docs/validation/OFFLINE_DATABASE_PREPARATION.md` — record the `-v4` baseline
  as the current state of `nba`, and note the date and duration of the applied
  run.

# Review evidence

Filled in before the card moves to `tasks/review/`.

## Automated validation

- Command:
- Result:

## Manual happy path

1.
2.
3.

Expected result:

## Manual sad path

1.
2.
3.

Expected result:

## Known limitations

- None.
