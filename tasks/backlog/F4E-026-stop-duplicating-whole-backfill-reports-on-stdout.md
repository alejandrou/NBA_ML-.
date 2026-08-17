---
id: F4E-026
title: Stop duplicating whole backfill reports on stdout
areas:
  - scraping
  - testing
priority: 50
depends_on: []
read:
  - src/nba_data/cli/main.py
  - src/nba_data/scraping/offline_reporting.py
validation:
  - uv run pytest tests/unit/test_offline_reporting.py tests/unit/test_offline_backfill.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

When a backfill or acquisition command is given `--output`, write the full report
to that file and print a summary to the terminal — instead of rendering the
entire document twice. Today the largest report in `reports/` is 178 MB, and the
CLI pretty-prints all of it to stdout.

# Evidence and current state

`_print_and_optionally_write_json` at
[`src/nba_data/cli/main.py:656-660`](../../src/nba_data/cli/main.py#L656-L660)
writes the file when `--output` is given and then calls
`console.print_json(data=data)` **unconditionally**. Seven commands use it:
`backfill offline`, `backfill stats`, `backfill player-stats`, `backfill
player-postseason-stats`, `acquisition acquire-nba-team-seasons`, `acquisition
dry-run-player-pages`, and `acquisition acquire-player-pages`.

Reports are large because they carry one entry per source, and quarantine
entries embed the parsed rows themselves —
[`offline_reporting.py:23`](../../src/nba_data/scraping/offline_reporting.py#L23)
declares `rows: tuple[dict[str, Any], ...]`. Measured in `reports/` (untracked,
local):

| File | Size |
|---|---|
| `offline-backfill-2000-2025.json` | **178,674,275 bytes** |
| `player-postseason-stats-backfill-2000-2025.json` | 1,662,648 bytes |
| `player-stats-backfill-2000-2025.json` | 1,337,077 bytes |
| `player-pages-acquisition-2000-2025.json` | 1,180,948 bytes |

The duplication is not hypothetical. `acquisition-2000-2025-20260530.json` and
`acquisition-2000-2025-20260530.run3.stdout.json` are both 255,263 bytes: the
operator redirected stdout and captured a byte-identical second copy of the
report the command had already written.

Two costs follow. Rich parses and renders the whole document to the terminal,
which for the 178 MB case is minutes of formatting no one reads; and
`json.dumps(data, indent=2)` at `:659` materializes the entire serialized
document as one string in memory before a byte is written.

# Human decisions or resources

- None.

# Acceptance criteria

- When `--output` **is** given: the full report is written to the file, and
  stdout receives a compact summary — every scalar field of the report, with each
  list-valued field replaced by its length — plus the resolved output path.
- When `--output` is **not** given: stdout still receives the complete document,
  unchanged. That is the only way to capture the report in that case, and the
  `reports/*.stdout.log` files prove operators do exactly that.
- The summary is derived generically from the report dictionary. It does not
  hard-code the field names of any one report type, so a new report shape needs
  no change here.
- The file is written by streaming to an open handle (`json.dump(data, handle,
  indent=2)`), not by building the whole string first. The written bytes are
  unchanged: same `indent=2` and same trailing newline.
- The file is still written before anything is printed, so a rendering failure
  cannot lose a completed run's report.
- Exit codes are unchanged, including the failure paths that print a report and
  then exit 1 (`acquisition acquire-nba-team-seasons`,
  `acquisition acquire-player-pages`).
- A test asserts both branches on a report carrying a list field: with `--output`,
  stdout does not contain an entry-level value and the file does; without
  `--output`, stdout contains it.

# Scope

`src/nba_data/cli/main.py` — `_print_and_optionally_write_json` and nothing else
in that file. Its tests.

# Out of scope

The **shape** of any report, including whether quarantine entries should embed
full rows — that is a report-contract question and `F4E-016` owns report
consolidation. Any change to JSON structure or to a JSONL/streaming format: the
reports are read back by `nba-data validate offline-database --backfill-report`
and by the F4E validators, so the on-disk document stays exactly as it is.
`backfill dry-run` and `acquisition dry-run-nba-team-seasons`, which call
`console.print_json` directly and have no `--output` flag. Log output — `F6-009`
owns logging.

# Impact

Operator-visible output for seven commands changes when `--output` is passed. No
report file changes, so `nba-data validate offline-database`, the F4E validators,
and every checked-in report stay valid. Any script that pipes stdout to a file
**while also** passing `--output` would capture the summary instead of the
document; the file it already asked for holds the full report.

# Implementation notes

Keep the helper's signature. This is a change of what it prints, not of how it is
called.

Rich's `print_json` parses the string it is given, so passing it a summary
dictionary rather than the full report is the whole fix on the rendering side.

The 178 MB report was produced by the full 2000-2025 offline backfill and is not
reproducible in a test. Assert the behavior on a small synthetic report with a
list field; the size is the motivation, not the test.

# Durable knowledge updates

- `docs/validation/OFFLINE_DATABASE_PREPARATION.md` — if it shows a command whose
  captured stdout is the report, correct it to use `--output` and read the file.

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
