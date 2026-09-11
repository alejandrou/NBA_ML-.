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
