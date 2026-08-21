---
id: F6-008
title: Add a serve command and document how to run the read API
areas:
  - api
  - documentation
  - testing
priority: 52
depends_on: []
read:
  - src/nba_data/cli/main.py
  - src/nba_data/api/app.py
  - README.md
validation:
  - uv run pytest tests/unit/test_api_foundation.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Give the API a supported way to start. `uvicorn` is a runtime dependency and the
app is finished, but how to run it is written down nowhere a user would look.

# Evidence and current state

`uvicorn>=0.30` is declared in `pyproject.toml:21`, under
`[project.dependencies]` rather than the dev group, so it ships with the package.

Searching the repository for `uvicorn` outside `pyproject.toml` returns three
hits, all inside completed task cards: `tasks/done/F5-004.md:104`,
`tasks/done/F5-005.md:253`, and
`tasks/done/F6-005-implement-api-database-readiness-endpoint.md:239`, which give
`uv run uvicorn nba_data.api.app:create_app --factory --port 8123`.

`tasks/done/` is documented as history that is never loaded by default
(`.agents/index.md`, "Never startup context"). `README.md` describes setup,
validation, the task lifecycle, the legacy scraper, and scraping limits — and
never mentions starting the API. `COMANDOS.md` is about the task workflow. The
only entry point declared in `pyproject.toml:34-35` is `nba-data`, which has
`info`, `settings`, `cache`, `backfill`, `acquisition`, and `validate`
subcommands, and nothing that serves.

`src/nba_data/api/__init__.py` already exports `create_app`, so the factory is
importable as `nba_data.api:create_app`.

# Human decisions or resources

- None.

# Acceptance criteria

- `nba-data serve` starts the API through `uvicorn`, using the existing
  `create_app` factory. No second application factory is introduced.
- The default bind address is **`127.0.0.1`**, never `0.0.0.0`. A local
  development default must not expose the API on every interface; the host is
  overridable with `--host` for anyone who means to.
- `--port` defaults to `8000`.
- `--reload` exists, defaults to **off**, and passes uvicorn an import string so
  reload actually works rather than failing on a non-importable callable.
- The command does not open a database connection itself. The engine is created
  by the app's `lifespan` (`src/nba_data/api/app.py:18-26`), and an unreachable
  database must still start the server and answer 503 on
  `GET /api/v1/health/ready` — the behavior `F6-005` established.
- A test monkeypatches `uvicorn.run` and asserts the arguments the command passes
  it: the application target, `factory=True`, the default host and port, and each
  overridden value. No test starts a real server or binds a port.
- `README.md` gains a short "Running the API" section with the command, the
  default address, and the two health routes. It states that the API is
  read-only and contacts no external source.
- `nba-data --help` lists `serve` with a one-line description.

# Scope

`src/nba_data/cli/main.py`, `README.md`, and one test module.

# Out of scope

Authentication, CORS, TLS, workers, process managers, containerization, and a
production deployment story — `F7-001` raises CORS as a frontend question and it
stays there. Changing `create_app`, the routers, the lifespan, or the settings.
Moving `uvicorn` between dependency groups. Adding a `--workers` flag: more than
one worker changes what the readiness route means per process, and nothing needs
it yet.

# Impact

One new CLI subcommand and one new README section. No API behavior changes. The
incantation currently buried in three done cards becomes the supported path, so
those cards stop being the de facto documentation.

# Implementation notes

Import `uvicorn` inside the command body, not at module scope. `src/nba_data/cli/main.py`
is imported by the console-script entry point for every subcommand, and no
`backfill` or `validate` invocation should pay for importing a web server.

Typer's option declarations in this module are hoisted to module-level constants
when they carry non-trivial configuration (`_ACQUISITION_OUTPUT_OPTION` and
friends at `:64-94`). Follow whichever form matches the neighbours.

There is no approval flag here on purpose. Serving is a read-only local action
that contacts nothing external, unlike every `--execute-approved-*` command in
this file. Do not model it on them.

# Durable knowledge updates

- `docs/architecture/API_ARCHITECTURE.md` — record the supported way to run the
  app if it currently describes only the factory.

# Review evidence

## Automated validation

- Command: `uv run pytest tests/unit/test_api_foundation.py`
- Result: 9 passed (7 existing + 2 new: default args, overridden args).
- Command: `uv run ruff check .`
- Result: All checks passed!
- Command: `uv run pytest`
- Result: 765 passed, 25 skipped.
- Command: `uv run nba-data --help`
- Result: `serve` listed with description "Serve the read-only API locally with
  uvicorn."

## Manual happy path

1. Ran `uv run nba-data serve --port 8123` in the background.
2. `curl http://127.0.0.1:8123/api/v1/health` → `{"status":"ok"}`, HTTP 200.
3. Server bound only to `127.0.0.1` (confirmed via `netstat`), not `0.0.0.0`.

Expected result: server starts without opening a database connection itself and
answers liveness immediately. Confirmed.

## Manual sad path

1. Same running server, local dev database not migrated to a ready schema.
2. `curl http://127.0.0.1:8123/api/v1/health/ready` → HTTP 503,
   `{"detail":"Database schema not ready"}`.
3. Server kept running and serving liveness throughout — did not crash or block
   on the unready database.

Expected result: readiness reports 503 while the server keeps running; the
F6-005 behavior held with a real (unready) database, not just a monkeypatched
one. Confirmed.

## Known limitations

- Manual verification used a local dev database that hadn't run migrations
  (schema-not-ready), not a fully unreachable one; the unreachable-database path
  is covered by F6-005's own existing tests, not re-verified here.
