---
id: F4E-032
title: Enforce the six-second acquisition delay floor centrally
areas:
  - scraping
  - testing
  - documentation
priority: 46
depends_on: []
read:
  - src/nba_data/config/settings.py
  - src/nba_data/scraping/client.py
  - src/nba_data/cli/main.py
  - tests/unit/test_rate_limited_client.py
  - tests/unit/test_settings.py
  - docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md
validation:
  - uv run pytest tests/unit/test_rate_limited_client.py tests/unit/test_settings.py
  - uv run pytest tests/unit/test_nba_team_season_acquisition.py tests/unit/test_player_page_acquisition.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
critical_actions:
  - No live request is needed and none is authorized. The floor is proved with a fake clock and a recording sleeper, exactly as `tests/unit/test_rate_limited_client.py` already does.
  - Do not rename, remove, weaken, or bypass the `--owner-approved` flags, the manifest schema, or the acquisition guards while editing the client or the CLI.
---

# Goal

Make the six-second minimum between Basketball Reference requests impossible to
configure away. `AGENTS.md` states the rule — "10 requests/minute default, never
above 20, at least 6 seconds apart" — but only the *upper* bound is enforced in
code. The lower bound is a default, and an environment override silently drops
below it.

Finding 3 of [the 2026-09-08 project and database audit](../../docs/validation/PROJECT_DATABASE_AUDIT_2026-09-08.md).

# Evidence and current state

- `src/nba_data/config/settings.py:22` declares
  `scraper_min_delay_seconds: float = Field(default=6.0, ge=0)`. The bound is
  `ge=0`, so `SCRAPER_MIN_DELAY_SECONDS=0` is accepted.
- `src/nba_data/config/settings.py:21` bounds requests per minute with
  `ge=1, le=20`, and `src/nba_data/scraping/client.py:52-54` raises on more than
  20 per minute. The ceiling is enforced twice; the floor is enforced nowhere.
- `src/nba_data/scraping/client.py:110-111` computes
  `rpm_delay = 60.0 / min(rpm, 20)` and
  `required_delay = max(scraper_min_delay_seconds, rpm_delay)`. With
  `scraper_min_delay_seconds=0` and `scraper_max_requests_per_minute=20` this is
  `max(0.0, 3.0)` — **3 seconds**, half the repository minimum. The audit
  reproduced `[3.0]` as the requested sleep from an in-memory limiter; no request
  was sent.
- `tests/unit/test_rate_limited_client.py:22-29` builds every limiter test from a
  `_settings()` helper pinned to `scraper_min_delay_seconds: 6` and
  `scraper_max_requests_per_minute: 10`, so no existing test exercises a
  below-floor override. `tests/unit/test_settings.py:16-17` asserts the defaults
  only.
- The 429 semantics disagree with `AGENTS.md` in the same file.
  `src/nba_data/scraping/client.py:31` defaults `max_429_retries: int = 1`, so
  the generic client sleeps at least 60 seconds and retries once
  (`client.py:89-97`). The two acquisition CLI paths already opt out explicitly:
  `src/nba_data/cli/main.py:706` and `src/nba_data/cli/main.py:830` both pass
  `max_429_retries=0`, asserted at `tests/unit/test_nba_team_season_acquisition.py:519`
  and `tests/unit/test_player_page_acquisition.py:488`. Only the untested default
  disagrees with "stop on 429".

# Human decisions or resources

- None.

# Acceptance criteria

- A single named module-level constant holds the six-second floor. Nothing
  restates the number as a literal in a second place.
- `Settings` rejects `scraper_min_delay_seconds` below the floor with a
  `ValidationError` naming the setting, the way an unrecognized `LOG_LEVEL` is
  rejected at `settings.py:35-45`. A rejected configuration fails at startup, not
  mid-acquisition.
- `BasketballReferenceClient._wait_for_rate_limit` also clamps to the floor, so a
  hand-constructed settings object, a future field change, or a test stub cannot
  produce a sub-floor sleep. Belt and braces: the settings validator states the
  rule, the limiter guarantees it.
- Offline tests cover the configuration boundary, driven by the existing
  `FakeClock`: `scraper_min_delay_seconds=0` with 20 requests/minute must sleep
  at least 6 seconds, not 3; a below-floor value must be refused by `Settings`;
  the floor value itself and a larger value are both accepted; a value above the
  floor still wins over `60 / rpm`.
- `max_429_retries` defaults to `0`, matching the `AGENTS.md` "stop on 429"
  instruction and the two acquisition CLI paths. The parameter stays, and
  `test_client_retries_once_after_429` keeps its coverage by passing
  `max_429_retries=1` explicitly.
- `Retry-After` handling is unchanged: `client.py:116-131` keeps parsing both
  seconds and HTTP-date forms, and the `max(retry_after, 60.0)` sleep before a
  caller-requested retry is untouched.
- `uv run nba-data settings` still reports `scraper_min_delay_seconds`
  (`cli/main.py:210`) and does not gain a secret.
- The full offline suite passes. No test contacts the network.

# Scope

`src/nba_data/config/settings.py`, `src/nba_data/scraping/client.py`,
`tests/unit/test_settings.py`, `tests/unit/test_rate_limited_client.py`, and
`.env.example` if the floor deserves a comment there.

# Out of scope

The cache-first read path, `HtmlCache`, the manifest schema, the acquisition
guards, and every `--owner-approved` flag. The 5xx retry policy
(`client.py:99-102`). Raising the default delay above 6 seconds or lowering the
20-per-minute ceiling. Any live request. Adding a new setting.

# Impact

Configuration surface: `SCRAPER_MIN_DELAY_SECONDS` gains a lower bound, so a
deployment that set it below 6 now fails to start instead of scraping too fast.
`.env.example:11` already ships `6`, so no checked-in configuration breaks.
Behavior: the generic client no longer retries a 429 by default; both acquisition
CLIs already behaved this way, so no acquisition path changes.

# Implementation notes

`AGENTS.md` outranks the code when the two disagree — that is why the 429 default
moves to match the documented rule rather than the rule being softened to match
the code. Say so in the review evidence so the next reader does not restore the
retry on suspicion.

Put the floor where both the settings model and the client can import it without
a cycle; `settings.py` already imports nothing from `scraping/`, and
`client.py:10` already imports `Settings`.

Prefer a `field_validator` over a bare `ge=6` if the resulting message is clearer
about *why* six seconds is the minimum — the operator reading that error is the
one about to run an acquisition.

# Durable knowledge updates

- `docs/domain/BUSINESS_RULES.md` or the scraping skill, if either states the
  pacing rule as a default rather than as an enforced floor. Check before
  editing; do not add a second copy of the rule.

# Review evidence

## What changed

- `src/nba_data/config/settings.py` gains module-level
  `MINIMUM_SCRAPER_DELAY_SECONDS = 6.0`. It is the only place the number lives in
  source. `scraper_min_delay_seconds` now defaults to that constant and drops
  `ge=0` in favor of a `field_validator` that names the environment variable in
  its message.
- `src/nba_data/scraping/client.py` imports the same constant and adds it as a
  third argument to the `max()` in `_wait_for_rate_limit`, so the limiter cannot
  produce a sub-floor sleep even from a `Settings` object that never passed
  validation.
- `src/nba_data/scraping/client.py` defaults `max_429_retries` to `0`.
  `AGENTS.md` says "stop on 429" and outranks the code, so the default moved to
  match the rule rather than the rule being softened to match the code. **Do not
  restore the `1` on suspicion.** The parameter still exists; the two acquisition
  CLI paths (`cli/main.py:706`, `cli/main.py:830`) already passed `0` explicitly
  and are unchanged.
- `.env.example` gains a one-line comment above `SCRAPER_MIN_DELAY_SECONDS`.
- Tests updated in `tests/unit/test_settings.py` and
  `tests/unit/test_rate_limited_client.py`.

Not changed, deliberately: `_retry_after_seconds` and the `max(retry_after, 60.0)`
sleep; the 5xx policy; the `--owner-approved` flags, manifest schema, and
acquisition guards; the cache-first read path.

- `.agents/skills/scraping-pipeline/SKILL.md` gains two rules: one saying the
  gap is a floor held in `MINIMUM_SCRAPER_DELAY_SECONDS` and enforced in both
  places, one saying the client stops on 429 by default and `max_429_retries` is
  an opt-in. Neither restates the six-second number — that stays in `AGENTS.md`,
  `README.md:128`, and the constant. The skill previously framed all pacing as
  defaults ("Respect 10 requests/minute default") and said "Stop or backoff on
  HTTP 429", which no longer describes what the code does.

`README.md:128` and `docs/domain/BUSINESS_RULES.md` needed no edit. The README
already states "minimum 6 seconds between requests" as a rule rather than a
default; `BUSINESS_RULES.md` does not discuss pacing at all, and adding it there
would be a second copy of the rule.

## Correction to this card's Impact section

The card says the 429 default change touches no acquisition path because "both
acquisition CLIs already behaved this way". That undercounts. Three call sites
construct the client without `max_429_retries`, so all three change behavior from
"retry once after sleeping at least 60s" to "stop on the first 429":

- `src/nba_data/cli/main.py:260` — `nba-data backfill acquire`, a real
  live-acquisition path behind `--execute-approved-manifest`. The card missed it.
- `scrape_main.py:28` — legacy, read-only under `AGENTS.md`. Unedited; it picks
  up the new default through the constructor.
- Any client built from `tests/unit/test_logging_configuration.py:108`, which
  makes no request.

Every change is in the safer direction and matches the `AGENTS.md` rule the card
set out to enforce, so the conclusion stands — but "no acquisition path changes"
was wrong, and `backfill acquire` is the one to keep an eye on.

## Automated validation

- Command: `uv run pytest tests/unit/test_rate_limited_client.py tests/unit/test_settings.py`
- Result: **23 passed** in 0.27s.

- Command: `uv run pytest tests/unit/test_nba_team_season_acquisition.py tests/unit/test_player_page_acquisition.py`
- Result: **29 passed** in 1.35s. Both still assert `max_429_retries == 0` on the
  constructed client; the CLI keeps passing it explicitly.

- Command: `uv run ruff check .`
- Result: **All checks passed!**

- Command: `uv run mypy src/nba_data`
- Result: **Success: no issues found in 70 source files.**

- Command: `uv run pytest`
- Result: **882 passed, 25 skipped, 7 warnings** in 29.24s. The 7 warnings are
  the pre-existing Starlette and peewee deprecations, unrelated to this card. No
  test contacted the network.

New tests, all offline and driven by the existing `FakeClock`:

| Test | Proves |
|---|---|
| `test_settings_rejects_a_delay_below_the_scraper_floor` | `0`, `3.0`, `5.999` each raise `ValidationError` naming `SCRAPER_MIN_DELAY_SECONDS` |
| `test_settings_accepts_the_floor_and_anything_slower` | `6.0` and `10.0` are accepted |
| `test_settings_rejects_a_below_floor_delay_from_the_environment` | the rejection happens at startup from the real env var, not only from a keyword argument |
| `test_client_never_sleeps_below_the_floor_for_an_unvalidated_delay` | delay `0.0` + 20 rpm sleeps `6.0`, not the `3.0` the audit reproduced |
| `test_client_honors_a_delay_slower_than_the_floor_and_the_rpm_gap` | `12.0` still beats both the floor and `60 / 20` |
| `test_client_stops_on_the_first_429_by_default` | one request, no sleep, `RateLimitExceededError` |

`test_client_retries_once_after_429` and `test_client_raises_after_repeated_429`
keep their coverage by passing `max_429_retries=1` explicitly.

## Manual happy path

1. `uv run nba-data settings`

Expected result: the table still lists `scraper_min_delay_seconds`, now `6.0`,
alongside `scraper_max_requests_per_minute`, `scraper_timeout_seconds`,
`scraper_cache_dir`, and `scraper_force_refresh`. No secret appears — no
`database_url`, no user agent. Observed exactly that.

2. `SCRAPER_MIN_DELAY_SECONDS=6 uv run nba-data settings`

Expected result: identical output. The floor value itself is legal.

3. `SCRAPER_MIN_DELAY_SECONDS=10 uv run nba-data settings`

Expected result: `scraper_min_delay_seconds: 10.0`. Slower than the floor is
always allowed.

## Manual sad path

1. `SCRAPER_MIN_DELAY_SECONDS=3 uv run nba-data settings`

Expected result: the command fails before doing any work with

```text
ValidationError: 1 validation error for Settings
scraper_min_delay_seconds
  Value error, SCRAPER_MIN_DELAY_SECONDS=3.0 is below the 6.0 second minimum
between Basketball Reference requests; that pacing floor is repository policy
and cannot be configured away
```

Observed verbatim. The old behavior was to accept it silently and, at 20
requests/minute, sleep 3 seconds between live requests.

2. `SCRAPER_MIN_DELAY_SECONDS=0 uv run nba-data settings`

Expected result: the same rejection, reporting `0.0`.

3. Set `SCRAPER_MIN_DELAY_SECONDS=3` in a local `.env` and run any acquisition
   command's `--help`.

Expected result: the same startup failure. A bad value can no longer survive to
the moment a request is about to be sent.

## Known limitations

- The settings validator and the limiter clamp state the floor twice by design —
  the validator explains the rule to an operator, the clamp guarantees it against
  a `Settings` object built in code. Both read the one constant, so they cannot
  drift apart.
- A caller can still pass `max_429_retries=1` deliberately. That is the escape
  hatch the two existing tests use; the card kept the parameter on purpose.
- Nothing here was exercised against a live Basketball Reference response, and
  none was authorized. The floor is proved with `FakeClock` and a recording
  sleeper.
