---
id: F4E-016
title: Consolidate backfill report validation across the stats reports
areas:
  - data-quality
  - testing
priority: 75
depends_on: []
read:
  - src/nba_data/cli/main.py
  - src/nba_data/validation/official_stats.py
  - reports/stats-backfill-2000-2025.json
  - reports/player-stats-backfill-2000-2025.json
  - reports/player-postseason-stats-backfill-2000-2025.json
validation:
  - uv run pytest tests/unit/test_official_stats_validation.py
  - uv run pytest tests/unit/test_offline_reporting.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Make `validate official-stats` reconcile **all three stats** backfill reports
against persisted stats totals instead of one, and make a partial row failure in a
backfill produce a non-zero exit instead of an exit-0 JSON blob. Without this,
no rebuild can be gated on a report, because the report and the totals it is
compared against describe different things.

# Evidence and current state

## One report is accepted; all stats tables are counted

[`validate_official_stats`](../../src/nba_data/cli/main.py#L450) takes a single
`--stats-backfill-report` path.
[`_backfill_report_issues`](../../src/nba_data/validation/official_stats.py#L898)
then computes `persisted_total_rows = sum(table_counts.values())` over **every**
`stats.*` table and compares it against that one report's `stats_loaded_rows`.

## The reports do not share a vocabulary

Measured from the checked-in reports:

| Report | Row-count key | Value |
|---|---|---|
| `stats-backfill-2000-2025.json` | `stats_loaded_rows` | 129,000 |
| `player-stats-backfill-2000-2025.json` | `rows_loaded_or_updated` | 96,336 |
| `player-postseason-stats-backfill-2000-2025.json` | `aggregate_rows_loaded_or_updated` + `team_rows_loaded_or_updated` | 40,528 + 40,528 |
| `offline-backfill-2000-2025.json` | *(core identities only; no stats rows)* | — |

**Only three reports contribute stats rows.** The offline report is core
identities only, contributes zero, and is **178 MB** — requiring it as a fourth
input would cost a large parse to add nothing. It is out of this card's
reconciliation.

[`_extract_backfill_summary`](../../src/nba_data/validation/official_stats.py#L952)
reads only the first vocabulary, from the report's top level. Two consequences,
both reachable today:

- Pass the **team-page** report and the check compares 129,000 against a
  persisted total that also includes ~177,392 player-page rows. It can never
  reconcile, and reports `backfill_row_mismatch` forever.
- Pass a **player-page** report and `stats_loaded_rows` is absent, so the check
  emits `stats_backfill_report_missing_field` and never compares anything.

The expected reconciled total across the three stats reports is **306,392** rows
(129,000 + 96,336 + 40,528 + 40,528). No command computes it.

Summing `count(*)` over all 33 `stats` tables in the live `nba` database gives
**306,392** — the reports and the database agree exactly. The **row-count
reconciliation** would therefore pass today, and the check that exists fails only
because it compares one report against all three stats reports' worth of rows.
That matters: it means the current `backfill_row_mismatch` output is a false
alarm, and a real mismatch would be indistinguishable from it.

**Overall validation would still fail, and an earlier revision of this card
wrongly said it would pass.** The row totals agree; the entry statuses do not.

## The reports carry failures the top level does not count

Measured from the checked-in reports:

| Report | Entries | `loaded` | `failed` | `skipped` |
|---|---|---|---|---|
| `stats-backfill-2000-2025.json` | 775 | 775 | 0 | 0 |
| `player-stats-backfill-2000-2025.json` | 2,515 | 1,872 | **577** | 66 |
| `player-postseason-stats-backfill-2000-2025.json` | 2,515 | 1,425 | 0 | 1,090 |

All 577 failures carry the single reason `"Player-page stats loader reported
failed rows."` **572 of them still loaded rows** — 25,640 rows in total across
the failed entries — so a failed entry is a *partial* load, not an abandoned one.
The 5 that loaded nothing are players whose every archived season failed.

The root cause is not in this card's scope: the failing rows are "Did not play"
placeholders whose `age` cell holds a reason string that cannot coerce into an
integer column. **F4E-022 owns that**, and after it lands this figure should be
zero. What matters here is the reporting contract, which is wrong regardless of
the count.

**The team report has a top-level failure counter; the two player reports do
not.** `stats-backfill-2000-2025.json` carries `stats_failed_rows`,
`stats_skipped_rows`, and `stats_quarantined_rows`, all `0`. The player reports
carry only `unresolved_players_or_seasons` (and its postseason equivalent), both
`0` — and "unresolved" means a grain that could not be looked up, which is a
different thing from a row that failed to load. **Nothing at the top level of
either player report reflects the 577.**

So the exit-code criterion below cannot be implemented by reading top-level
counters alone. The implementation must either aggregate `entries[].status`, or
add explicit failure counters to the two player producers. That is a real choice
and is made in the acceptance criteria rather than left to the implementer.

## Partial row failures exit 0

[`backfill_player_stats`](../../src/nba_data/cli/main.py#L352) ends with
`_print_and_optionally_write_json(report.to_dict(), output)` and returns. There is
no exit-code branch on the report's failure counters, so a run that fails or
quarantines rows still exits 0. The postseason and team-page backfill commands
end the same way. By contrast `validate offline-database` and
`validate official-stats` both `raise typer.Exit(code=1)` when their report does
not pass — so the validation commands signal failure and the backfill commands
that produce their input do not.

# Human decisions or resources

- None.

# Acceptance criteria

- `validate official-stats` gains **one distinctly typed flag per producer** —
  `--team-stats-report`, `--player-stats-report`,
  `--player-postseason-stats-report` — each accepting at most one path. The flag
  identifies the report kind, so nothing infers a kind from the file's contents.
  The command continues to work with none supplied.
- Reconciliation sums each supplied report's contribution using **that
  producer's** vocabulary, selected by which flag carried it, and compares the sum
  to the persisted total. If a report does not contain the key its flag implies,
  that is a named issue — the reader validates the expected key rather than
  searching for any key it recognizes.
- Supplying an incomplete set is itself reported — a partial set must not look
  like a reconciled archive. The report names which producers are missing.
- **Each of the three producers emits explicit top-level failure counters** —
  at minimum `entries_failed` and `rows_failed` — computed from its own entries.
  The team report already has equivalents; the two player producers gain them.
  This is preferred over teaching the validator to aggregate `entries[].status`,
  because the producer already knows the answer and every consumer would
  otherwise re-derive it, but the validator must still treat a report lacking the
  counters as a named issue rather than as a clean run.
- Each backfill command exits non-zero when its report carries nonzero failure,
  quarantine, or unresolved counters, and exits 0 only on a clean run. The JSON
  report is still printed and still written to `--output` in both cases.
- Tests cover: the three stats reports reconciling to 306,392 against matching
  table counts; one report missing; a report passed under the wrong flag, so the
  expected key is absent; a report with nonzero `rows_failed`; a report missing
  the new counters entirely; and each backfill command's non-zero exit path.
- **The old `--stats-backfill-report` flag is removed**, and supplying it exits
  non-zero with a message naming `--team-stats-report` as its replacement. It is
  not silently accepted and not silently re-interpreted: its current meaning —
  "reconcile this one report against every stats table" — is the defect this card
  fixes, so keeping it working would keep the defect reachable.

# Scope

- `src/nba_data/cli/main.py` — the three typed `validate official-stats` report
  flags and the exit branches of the three backfill commands.
- `src/nba_data/validation/official_stats.py` — `_extract_backfill_summary`,
  `_backfill_report_issues`, and the summary shape they feed.
- `tests/unit/` for the CLI exit codes and the reconciliation matrix.

# Out of scope

Changing what a backfill writes, or what the report contains beyond what
reconciliation needs. Unifying the report schemas into one — this card
reads each vocabulary as it is. The coverage invariant, which is F4E-018.
Re-running any backfill.

# Impact

The `validate official-stats` CLI surface and its exit code; the exit codes of
all three stats backfill commands, which any script or CI step invoking them
will now observe. `docs/validation/OFFLINE_DATABASE_PREPARATION.md` and
`COMANDOS.md` document these invocations and must match.

# Implementation notes

This card is a prerequisite for gating the future rebuild-and-diff card, and is
independently valuable now: it is the only thing that would make a partial
backfill visible at the command line.

The typed flags are what make this implementable. A single repeatable generic
flag would hand the reader an anonymous JSON object and force it to guess the
producer from the keys present — and the checked-in reports carry no
`report_kind` or `schema_version` to guess from. Distinct flags supply the kind
out of band, cost no change to any producer, and work against the reports already
on disk. Adding a `report_kind` discriminator to the producers is the alternative
and is strictly more work for the same result; if it is ever added, the flags can
then validate it.

Sum per-report contributions through a small explicit mapping from report kind to
its row-count keys. Do not teach one function all three vocabularies inline.

Note that `unsupported_synthetic_or_tot_rows` in the postseason report (10,600)
is an expected skip under ADR 0007, not a failure. Do not fold it into the
failure counters. The same applies to the postseason report's 1,090 `skipped`
entries — players with no postseason appearances — which are the normal case, not
a defect.

**Expect the exit-code change to make the player-stats backfill fail on the
current cache**, because of the 577 placeholder failures described above. That is
correct behavior and the reason F4E-022 exists. Do not weaken the exit rule to
accommodate it, and do not make this card depend on F4E-022: the reporting
contract is wrong on its own terms and is worth fixing whichever lands first. If
this card lands first, record the 577 as the known baseline in
`OFFLINE_DATABASE_PREPARATION.md` so the failure is documented rather than
surprising.

# Durable knowledge updates

- `docs/validation/OFFLINE_DATABASE_PREPARATION.md` — record the full validation
  invocation with the three stats reports and the new exit-code contract.
- `COMANDOS.md` — update the documented backfill and validation commands.

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
