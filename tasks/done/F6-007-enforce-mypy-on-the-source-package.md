---
id: F6-007
title: Make mypy a real gate on the source package
areas:
  - testing
priority: 42
depends_on:
  - F4E-022
read:
  - pyproject.toml
  - .github/workflows/ci.yml
  - README.md
validation:
  - uv run mypy src/nba_data
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Either enforce mypy or stop shipping it. It is installed, configured, and never
run — by CI, by the README's validation list, or by the PowerShell preflight.
This card enforces it on `src/nba_data`, which currently means fixing eight
errors.

# Evidence and current state

`pyproject.toml:26-32` puts `mypy>=1.11` in the dev group, and `:71-74` configures
it (`python_version = "3.11"`, `warn_unused_configs`, `ignore_missing_imports`).
Nothing invokes it: `.github/workflows/ci.yml` runs `ruff check` and `pytest` in
the offline job and nothing else; `README.md:20-27` lists
`validate_tasks.py`, `ruff`, `pytest`, and `git diff --check`;
`scripts/dev/start-dev.ps1` is described as the lint-and-test preflight.

`uv run mypy src/nba_data` today reports **8 errors in 6 files** across 65
checked source files:

| Location | Error |
|---|---|
| `scraping/parsers/team_season.py:83` | unsupported right operand for `in` on `str \| AttributeValueList \| None` |
| `scraping/parsers/team_season.py:83` | `Tag.get` second argument typed `list[Never]` |
| `scraping/parsers/team_season.py:101` | returns `list[str \| AttributeValueList]`, declared `list[str]` |
| `scraping/parsers/player_page.py:53` | `object` passed where `BeautifulSoup` expected |
| `api/services/readiness.py:109` | `SQLAlchemyError` has no attribute `orig` |
| `validation/offline_database.py:511` | bare `type` has no attribute `id` |
| `scraping/player_page_acquisition.py:417` | `Select[tuple[str \| None]]` assigned to `Select[tuple[str]]` |
| `scraping/offline_player_postseason_stats_backfill.py:163` | `object` passed where `Path` expected |

None of these is a live defect — every one is a signature or narrowing gap where
the runtime value is correct and the declared type is wider than reality. That is
the argument for the gate, not against it: eight is a cheap number to fix, and it
only stays cheap if something enforces it.

# Human decisions or resources

- None.

# Acceptance criteria

- `uv run mypy src/nba_data` exits clean.
- CI runs it. The step lives in the offline `test` job, after `ruff`, and fails
  the build on any error.
- `README.md`'s validation block lists the mypy command alongside `ruff` and
  `pytest`, in the order CI runs them.
- Every fix narrows or corrects a type. No error is silenced with a bare
  `# type: ignore`; where one is genuinely unavoidable it is specific
  (`# type: ignore[code]`) and carries a comment saying why.
- **No runtime behavior changes.** The full offline suite passes with the same
  count it passes with today.
- The BeautifulSoup errors are fixed by narrowing what the parser accepts and
  returns, not by loosening the annotations to `Any`.
- `api/services/readiness.py:109` is fixed by typing the parameter as the
  exception class that actually carries `orig` — `DBAPIError`, the base of the
  `OperationalError` the caller passes — rather than by reaching through
  `getattr` on a wider type.
- `validation/offline_database.py:508` types its `child` and `parent` parameters
  as declarative model classes rather than bare `type`.
- `ignore_missing_imports = true` stays. Third-party stubs are not this card's
  problem.
- The mypy invocation names `src/nba_data` explicitly in both CI and the README,
  so the gate's scope is visible rather than implied by the working directory.

# Scope

`pyproject.toml` if a setting must change, `.github/workflows/ci.yml`,
`README.md`, and the six source files listed above.

# Out of scope

Type-checking `tests/`, `scripts/`, `alembic/`, or the legacy prototype
(`scrap/`, `models/`, `db_manager/`, `utils/`, `scrape_main.py`) — the legacy
tree is read-only and `ruff` already excludes it. Turning on `strict`,
`disallow_untyped_defs`, or any other tightening: this card enforces the current
configuration, and raising the bar is a separate decision. Adding stub packages.
Refactoring any of the six files beyond what the fix requires.

# Impact

CI gains a step and a new failure mode: an unannotated or wrongly annotated
change now fails the build. Six source files gain narrower types. `README.md` and
`scripts/dev/start-dev.ps1` should agree on the validation set — update the
script if it enumerates the commands.

# Implementation notes

**Do not start before `F4E-022` is in `tasks/done/`.** One of the eight errors is
in `scraping/offline_player_postseason_stats_backfill.py`, which that card
modifies, and `scraping/normalizers/player_page.py` is in the same diff. Fixing
types under it means resolving a conflict for no reason.

Fix the errors first and add the CI step last, so the step is added to a tree
that already passes.

Run mypy from the repository root. The `[tool.mypy]` block in `pyproject.toml` is
found relative to the working directory, and a run from elsewhere silently uses
different settings.

If a fix looks like it needs a behavior change to satisfy the checker, stop and
report it. That would mean the annotation was documenting a real defect, which is
a different card.

# Durable knowledge updates

- `docs/validation/TESTING_STRATEGY.md` — record mypy as part of the offline
  validation set once it is enforced.

# Review evidence

## Automated validation

- Command: `uv run mypy src/nba_data`
- Result: `Success: no issues found in 71 source files` (exit 0).

- Command: `uv run ruff check .`
- Result: `All checks passed!`

- Command: `uv run pytest`
- Result: `872 passed, 25 skipped, 7 warnings in 15.86s`. No test file was
  added, removed, or edited, so the collected count is unchanged by
  construction.

- Command: `uv run python scripts/validate_tasks.py`
- Result: `Task validation passed.`

## Manual happy path

1. `uv run mypy src/nba_data`
2. `uv run ruff check .`
3. `uv run pytest`

Expected result: all three exit 0; mypy reports `Success: no issues found in 71
source files`. `README.md`, `docs/validation/TESTING_STRATEGY.md`,
`scripts/dev/start-dev.ps1`, and `.github/workflows/ci.yml` all name the same
command, `uv run mypy src/nba_data`, in the same position: after Ruff, before
Pytest.

## Manual sad path

1. Append a deliberately wrong return to any module under `src/nba_data`, e.g.
   `def _probe() -> int: return "not an int"` in
   `src/nba_data/validation/__init__.py`.
2. `uv run mypy src/nba_data`
3. Remove the added function.

Expected result: step 2 exits **1** with
`error: Incompatible return value type (got "str", expected "int")
[return-value]` and `Found 1 error in 1 file (checked 71 source files)`. This
was run during implementation and behaved exactly so; the file was restored and
verified byte-identical. The same command is now a CI step, so that failure
fails the build.

## Known limitations

- **The card's error inventory was stale.** It described 8 errors in 6 files
  across 65 source files. `F4E-024`, `F4E-029` and `F4E-030` landed after the
  card was written, and the real starting point was **26 errors in 9 files
  across 71 source files**. All 26 are fixed. The three files beyond the card's
  list are `validation/stats_coverage.py`, `validation/official_stats.py` and
  `validation/__init__.py`; every change in them is a type fix, not a
  refactor.
- **`_missing_parent_count` gained an explicit `parent_id` argument.** The card
  asked for `child` and `parent` to be typed as declarative model classes. They
  now are (`type[Base]`), but `Base` declares no columns of its own, so
  `parent.id` cannot type-check through it. A `Protocol` does not work either:
  SQLAlchemy's `Mapped[int]` resolves to `int` on an instance and
  `InstrumentedAttribute[int]` on the class, which no protocol member can
  express. The parent's id column is therefore passed explicitly at the seven
  call sites. The emitted SQL is unchanged.
- **Shape errors in `parse_stats_coverage_artifact` are now named.** Replacing
  the mis-coded `# type: ignore` comments with real narrowing means a malformed
  artifact — a non-array `entries`, a non-object `cache_fingerprint`, a
  `season_type` that is neither `regular` nor `postseason` — now raises
  `StatsCoverageShapeError` with the offending field named, where some of those
  shapes previously produced a bare `TypeError`/`KeyError` wrapped in a generic
  message or, for `season_type`, passed through unvalidated. This is the
  behavior that class was introduced for, and no well-formed artifact reaches a
  different outcome. All existing artifact tests pass unchanged.
- `_serialize_coverage_keys` lost its `team_stint` keyword. The flag only ever
  repeated what the key's width already says, so the function now narrows on
  `len(key) == 4` and both call sites pass the keys alone. Output is
  byte-identical for every key the dimension loop produces.
- The gate enforces the existing `[tool.mypy]` settings only. `strict`,
  `disallow_untyped_defs`, and stub packages remain out of scope, and
  `ignore_missing_imports = true` is untouched. `pyproject.toml` needed no
  change.
