---
id: F6-009
title: Configure application logging at the CLI and API entry points
areas:
  - api
  - scraping
  - testing
priority: 58
depends_on: []
read:
  - src/nba_data/config/settings.py
  - src/nba_data/cli/main.py
  - src/nba_data/api/app.py
  - src/nba_data/scraping/client.py
validation:
  - uv run pytest tests/unit/test_settings.py tests/unit/test_rate_limited_client.py tests/unit/test_api_foundation.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Make `LOG_LEVEL` do what its name promises. Nothing in `src/` ever configures
the logging system, so every `logger.info` the codebase emits is discarded and
every warning is printed by Python's last-resort fallback without a timestamp,
level, or logger name.

# Evidence and current state

`ripgrep` over `src/`, `tests/`, and `scripts/` for `basicConfig`, `dictConfig`,
and `logging.config` returns **no matches**. The only two hits for `log_level`
are its definition at `src/nba_data/config/settings.py:16` and its display at
`src/nba_data/cli/main.py:113`, inside `nba-data settings`. The setting is shown
to the operator and then never applied to anything.

What that costs, concretely:

- `src/nba_data/scraping/client.py:85` logs `"Requesting %s"` at INFO on every
  network request, and `:61` logs every cache hit. The root logger's default
  level is WARNING and no handler is installed, so **an approved live
  acquisition produces no record of which URLs were requested.** The only
  surviving evidence is the JSON report and the cache files themselves.
- `src/nba_data/api/services/readiness.py:49-61` logs a warning for every
  not-ready outcome, and `src/nba_data/api/app.py:31` logs the exception behind
  every 500. These do reach stderr through `logging.lastResort`, but that handler
  emits the bare message with no timestamp, level, or logger name, which is not
  usable as a server log.
- `uvicorn` does not close this gap. Its logging configuration sets up the
  `uvicorn`, `uvicorn.error`, and `uvicorn.access` loggers; it does not attach a
  handler to the root logger, so `nba_data.*` records are unaffected by running
  the API under it.

# Human decisions or resources

- None.

# Acceptance criteria

- A single `configure_logging(settings)` helper exists — `src/nba_data/config/`
  is the natural home — and is the only place in `src/` that touches global
  logging state.
- It applies `settings.log_level` to the `nba_data` logger, attaches exactly one
  stream handler to stderr, and uses a format carrying at least timestamp, level,
  logger name, and message.
- It is **idempotent**: calling it twice does not attach a second handler and does
  not double every line. A test asserts this directly by calling it twice and
  counting handlers.
- An unrecognized `LOG_LEVEL` fails loudly with a clear message naming the
  setting, rather than silently defaulting. Whether that is enforced in
  `Settings` as a validator or in the helper is the implementer's call, but it is
  enforced in exactly one of them, and a test covers a bad value.
- It is called from the Typer application callback in `src/nba_data/cli/main.py`
  so every `nba-data` subcommand is covered by one call site, and from the
  FastAPI `lifespan` in `src/nba_data/api/app.py`.
- It is **never called at import time** — not at module scope, not in
  `create_app()` outside the lifespan. Importing `nba_data` must leave the
  logging system untouched, so the test suite's output is unchanged.
- With `LOG_LEVEL=INFO`, a `BasketballReferenceClient` cache hit emits a
  formatted INFO line. A test asserts this through `caplog` or a captured
  handler, without making a network request.
- The full offline suite still passes with no new output noise. If any test
  begins emitting log lines, that is the import-time rule being broken.

# Scope

`src/nba_data/config/` (the new helper), `src/nba_data/config/settings.py` if the
level is validated there, `src/nba_data/cli/main.py` (callback), and
`src/nba_data/api/app.py` (lifespan). Tests for the helper and its two call sites.

# Out of scope

Adding new log statements, changing existing levels or messages, structured or
JSON logging, log files, rotation, request-id correlation, and any log shipping.
Uvicorn's own access log. Changing what `nba-data settings` prints. `README.md`
and `.env.example` already carry `LOG_LEVEL`; no documentation restructuring is
needed beyond correcting anything that is wrong.

# Impact

Every `nba-data` subcommand and the API process gain real logs. Operator-visible
output changes: warnings that previously appeared bare now carry a level and
timestamp, and INFO becomes visible at the default level. The rate-limited
client's request log becomes the audit trail for any future approved
acquisition, which is the main reason this is worth doing before the next one.

# Implementation notes

Configure the `nba_data` logger rather than the root logger. Every module in the
package uses `logging.getLogger(__name__)`, so one package-level logger covers
all of them without taking over logging for dependencies or for a host
application that imports this package.

The idempotence requirement is not decoration: the CLI callback and the API
lifespan can both run in one process during tests, and `pytest` itself installs
handlers.

Do not weaken, reroute, or add logging to the acquisition approval guards. This
card gives their existing messages somewhere to go; it does not touch the
interlock.

# Durable knowledge updates

- `docs/validation/PLAYER_PAGE_CACHE_ACQUISITION.md` and
  `docs/validation/NBA_TEAM_SEASON_CACHE_ACQUISITION.md` — if either describes
  capturing a run log, record that the request log now depends on `LOG_LEVEL`
  being at INFO.

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
