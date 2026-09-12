---
id: F6-010
title: Clean up the runtime dependency list
areas:
  - testing
  - documentation
priority: 38
depends_on: []
read:
  - pyproject.toml
  - tests/unit/test_legacy_team_scrapers.py
validation:
  - uv run pytest tests/unit/test_legacy_team_scrapers.py tests/unit/test_legacy_team_season_scrapers.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Make `[project.dependencies]` describe what the platform actually needs at
runtime. Three of its fifteen entries do not: two are imported nowhere in the
repository, and one exists only for the read-only legacy prototype.

# Evidence and current state

Searched across `src/`, `tests/`, `scripts/`, `scrap/`, `models/`, `db_manager/`,
`utils/`, and `scrape_main.py`:

- **`tenacity>=8.3`** (`pyproject.toml:19`) — zero occurrences anywhere in the
  repository, including comments. Retry behavior is hand-written in
  `src/nba_data/scraping/client.py:79-105`.
- **`requests>=2.32`** (`pyproject.toml:16`) — zero import statements. The only
  seven matches are offline tests asserting the *absence* of the import, such as
  `tests/unit/test_offline_loader.py:167`:
  `assert "import requests" not in module_source`. HTTP is `httpx`
  (`src/nba_data/scraping/client.py:8`).
- **`peewee>=3.17`** (`pyproject.toml:22`) — imported only by the legacy
  prototype: `models/player/*.py`, `models/team/*.py`, and
  `db_manager/db_conf.py`. Nothing under `src/nba_data/` touches it. It is still
  needed for tests, because `tests/unit/test_legacy_team_scrapers.py:4` imports
  `db_manager.team_operations.team_operations`, which reaches peewee
  transitively. Its deprecation warning is emitted six times in every `pytest`
  run (`peewee.py:252`, `"to_field" has been deprecated`), which is six of the
  seven warnings the suite reports.

The rest of the list is genuinely used, including two that look unused and are
not: `lxml` is the parser backend at
`src/nba_data/scraping/parsers/team_season.py:37` (`BeautifulSoup(html, "lxml")`),
and `rich` is the CLI console at `src/nba_data/cli/main.py:63`.

# Human decisions or resources

- None.

# Acceptance criteria

- `tenacity` and `requests` are removed from `[project.dependencies]`.
- `peewee` moves from `[project.dependencies]` to the `dev` dependency group. It
  is a test-only dependency of a read-only prototype, not a runtime dependency of
  the platform.
- Each of the three changes carries a one-line comment or is explained in the
  card's review evidence, so the next reader does not restore them on suspicion.
- `uv.lock` is regenerated in the same change and committed with it.
- The full offline suite passes with the same test count, including both legacy
  test modules, which must still import `db_manager` and `scrap` successfully.
- CI passes. Its `uv sync --all-groups` installs the dev group, so the legacy
  tests keep their peewee.
- Installing the project **without** the dev group no longer pulls peewee,
  tenacity, or requests. Verify this concretely — a `uv pip install .` into a
  throwaway environment, or `uv tree` — and record what was checked.
- The legacy tree itself is not edited. It stays read-only.

# Scope

`pyproject.toml` and `uv.lock`.

# Out of scope

Removing, rewriting, or porting the legacy prototype. Deleting the legacy tests —
they are the only coverage that prototype has. Upgrading any version bound.
Splitting the dev group into finer groups. Moving `uvicorn` (`F6-008` documents
serving as a supported command, which keeps it a runtime dependency). Silencing
the peewee deprecation warning: with peewee in the dev group the warning still
appears in test runs, and suppressing it is a separate decision.

# Impact

The installed footprint of `nba-data-platform` shrinks by three packages for
anyone who is not running the tests. No source file changes and no behavior
changes. `uv.lock` changes, so the diff is large but mechanical.

# Implementation notes

Regenerating the lock requires network access to the package index, exactly as
`uv sync` in the README's setup does. It contacts no data source and writes
nothing outside the repository.

Confirm the two legacy test modules still pass **before** concluding the peewee
move is safe. They are the reason peewee stays installed at all, and they import
through `tests/conftest.py`, which puts the repository root on `sys.path`.

If any of the three turns out to be needed by `etl_process.ipynb`, that notebook
is excluded from ruff and is not part of the source of truth — note it and
proceed rather than keeping a runtime dependency for it.

# Durable knowledge updates

- None.

# Review evidence

## Changes

- `pyproject.toml`: removed `requests` and `tenacity` from
  `[project.dependencies]`, with one comment saying why (HTTP is `httpx`; retries
  are hand-written in `scraping/client.py`). Moved `peewee` to the `dev` group,
  with a comment naming the legacy tests that need it.
- `uv.lock`: regenerated with `uv lock`. No `--upgrade`. It removes four packages:
  `requests` 2.34.0, `tenacity` 9.1.4, and the two packages only `requests` pulled
  in, `urllib3` 2.7.0 and `charset-normalizer` 3.4.7. `peewee` moves to the dev
  group. No other package's version changed. `idna` and `certifi` stay because
  `httpx` needs them.
- Legacy tree not touched. `rg` found no use of any of the three in
  `etl_process.ipynb`.

## Automated validation

- Baseline before any change: `uv run pytest` gave **949 passed, 27 skipped, 7 warnings**.
- `uv tree --invert --package requests --package tenacity --package peewee` (before):
  all three are direct dependencies of `nba-data-platform` only. Nothing else
  depends on them.
- `uv run pytest tests/unit/test_legacy_team_scrapers.py tests/unit/test_legacy_team_season_scrapers.py`:
  **10 passed, 6 warnings** (the six peewee `to_field` warnings). Both modules
  still import `db_manager` and `scrap`.
- `uv run ruff check .`: **All checks passed!**
- `uv run pytest`: **949 passed, 27 skipped, 7 warnings**, the same count as the baseline.
- `uv sync --all-groups` (exact sync, the same command as CI) uninstalled
  `charset-normalizer`, `requests`, `tenacity`, and `urllib3` from `.venv` and kept
  `peewee`. Running `uv run pytest` again on that pruned environment gave
  **949 passed, 27 skipped, 7 warnings**.
- No-dev check, `uv tree --no-dev`: no `peewee`, `tenacity`, `requests`,
  `urllib3`, or `charset-normalizer`. `uv tree` (with dev): `peewee v4.0.5 (group: dev)`.
- Throwaway install: `uv venv --python 3.11 <scratch>/nodev-venv` then
  `uv pip install --python <scratch>/nodev-venv .`. `uv pip list` shows 37
  packages and none of the five removed ones. `find_spec` reports `peewee`,
  `tenacity`, and `requests` as absent, and `httpx`, `lxml`, `rich`, and `uvicorn`
  as present. `nba-data --help` from that venv exits 0.
- `git diff --check`: clean. The only warning is Git's LF→CRLF notice for `uv.lock`.
- `uv run python scripts/validate_tasks.py`: passed after each card move.

## Manual happy path

1. `uv sync --all-groups`
2. `uv run pytest`
3. `uv tree --no-dev | Select-String 'peewee|tenacity|requests'`

Expected result: the sync removes `requests`, `tenacity`, `urllib3`, and
`charset-normalizer` if they are still installed, and keeps `peewee`. The tests
report 949 passed, 27 skipped, 7 warnings. Step 3 prints nothing.

## Manual sad path

1. Create a fresh venv and install the project without the dev group:
   `uv venv $env:TEMP\f6010; uv pip install --python $env:TEMP\f6010 .`
2. `& $env:TEMP\f6010\Scripts\python.exe -c "import peewee"`
3. `& $env:TEMP\f6010\Scripts\python.exe -c "import sys; sys.path.insert(0, '.'); import db_manager.db_conf"`

Expected result: steps 2 and 3 both fail with `ModuleNotFoundError: No module named 'peewee'`.
The legacy prototype needs the dev group, and the platform package does not.
`nba-data --help` from the same venv still works.

## Known limitations

- The peewee `to_field` deprecation warning still appears six times per test
  run, as the card's out-of-scope section expects.
- An existing `.venv` keeps `requests` and `tenacity` until someone runs an exact
  `uv sync`. `uv run` alone does not remove extra packages.
- The `uv.lock` diff shows an LF→CRLF warning on this Windows checkout. The file
  itself is still LF.
