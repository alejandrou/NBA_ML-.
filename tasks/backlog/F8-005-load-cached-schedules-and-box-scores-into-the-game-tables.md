---
id: F8-005
title: Load cached schedules and box scores into the game tables
track: data
areas:
  - scraping
  - data-quality
  - testing
  - documentation
priority: 96
depends_on:
  - F8-002
  - F8-004
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/validation/PER_GAME_ACQUISITION_PILOT.md
  - docs/domain/BUSINESS_RULES.md
  - docs/architecture/SYSTEM_DESIGN.md
  - src/nba_data/scraping/parsers/box_score.py
  - src/nba_data/scraping/parsers/league_schedule.py
  - src/nba_data/scraping/game_season_planning.py
  - src/nba_data/validation/game_pilot.py
  - src/nba_data/validation/parser_contracts.py
  - src/nba_data/scraping/loaders/team_season_stats.py
  - src/nba_data/scraping/offline_stats_backfill.py
  - src/nba_data/db/models/core.py
  - src/nba_data/db/models/stats.py
validation:
  - uv run pytest tests/unit/test_game_loader.py tests/unit/test_offline_games_backfill.py tests/unit/test_box_score_parser.py tests/unit/test_league_schedule_parser.py tests/unit/test_parser_contracts.py tests/unit/test_game_pilot_validation.py
  - uv run pytest tests/integration/test_game_loader_postgres.py
  - uv run ruff check .
  - uv run mypy src/nba_data
  - uv run pytest
  - bash scripts/validate_database.sh
  - uv run python scripts/validate_tasks.py
critical_actions:
  - Running `backfill games` against the persistent nba database — only from merged origin/main, after F8-002's revision is applied there, and with the owner's approval (F8-006). Review uses a disposable database.
---

# Goal

An offline, idempotent `nba-data backfill games` that turns cached schedule and
box-score pages into `core.games`, `stats.team_game_totals`, and
`stats.player_game_totals`. It enforces every cross-table rule the schema
cannot (F8-002, "Out of scope") before writing, and reports per-season
coverage, so twelve seasons can be loaded and trusted without reading a page by
hand.

# Evidence and current state

- The parsers exist and are tested against trimmed real pages:
  `parse_box_score_page` (heading → `game_type`, venue, attendance blank vs 0,
  per-team totals and `totals_seconds`, player lines with participation, reason,
  starter, seconds, 15 counters, plus-minus, and `inactive_player_ids`) and
  `parse_league_schedule_page` (`ScheduleGame`: date, teams, points, overtime,
  start time "7:30p", attendance, arena, notes, `game_id`).
- The inactive list keeps ids only (`parsers/box_score.py:445-467`), but
  `core.players.full_name` is not null (`db/models/core.py:88`). Inactive-only
  players (pilot finding 9: `youngpa01`, `topicni01`) cannot be created without
  their link text.
- The pilot reconciliation (`validation/game_pilot.py`) already checks score
  agreement across schedule, scorebox, team totals, and line score, player sums
  against team totals, minutes, and participation, from the cache only. Its
  allowances (team turnovers, per-line second rounding, 0:00 lines without
  plus-minus) are the loader's too.
- Parser versions live in `validation/parser_contracts.py`
  (`current_parser_version(...)`); the box-score and schedule parsers have no
  contract entry yet.
- No page flags a neutral site (finding 4); the box score venue line always
  carries the city ("Accor Arena, Paris, France").
- The F8-001 cache holds 30 real games across 1999-2026, with the trimmed
  fixtures in `tests/fixtures/html/`.

# Human decisions or resources

- [x] **Only finished games are loaded**: a game is written when its box score is
      cached and passes the gates, with `status = 'final'`. Schedule rows
      without a box score are coverage, not rows. Scheduled games belong to the
      current-season card (F8-008).
- [x] **The season comes from the schedule page** that lists the game; a game
      whose two team-seasons are not in `core` is quarantined with
      `missing_team_season`, never created.
- [x] **Missing players are created from box-score links**: id from the link,
      `full_name` from the link text, no player-season. The inactive-list parse
      keeps the link text (a parser change, contract version bumped).
- [x] **Neutral site** is derived per season after loading: a game is neutral
      when its venue city (the text after the first comma) differs from the
      city of most of the home team's home games that season; no venue →
      `NULL`. This marks London, Paris, Mexico City, Tokyo, the Las Vegas Cup
      games, and the 2020 bubble, and survives arena renames such as
      Staples Center → Crypto.com Arena (same city). Each season's neutral list
      is in the report for review.
- [x] **Cup final plus-minus**: when every played line of a `cup_final` game has
      plus-minus 0, every line stores `NULL` (finding 3).
- [x] **Line-score conflicts are warnings**: per-period scores are not stored
      (F8-002), so a line score that disagrees with play-by-play or quarter boxes
      is reported, not quarantined. A final-score disagreement is quarantined.
- [x] **Heading confirmation**: a fetched game whose heading is play-in or
      playoffs is loaded with that `game_type` and listed in the report; an
      `unknown` heading is quarantined.
- [x] **One transaction per game.** A quarantined game writes nothing; the
      others load.

# Acceptance criteria

- `scraping/loaders/games.py`: `load_game(session, parsed_schedule_row,
  parsed_box_score, lineage)` writes one `core.games` row, two
  `stats.team_game_totals` rows, and one `stats.player_game_totals` row per
  player line and inactive entry, upserting on the natural keys
  (`basketball_reference_game_id`; `(game_id, team_season_id)`;
  `(game_id, player_id)`). It never commits.
- Gates before any write, each with a named quarantine reason:
  `unknown_game_type`, `missing_team_season`, `team_mismatch` (box score teams ≠
  schedule teams), `score_mismatch` (schedule ≠ scorebox ≠ team totals `pts`),
  `tied_score`, `missing_team_totals` (no `pts` or `totals_seconds`),
  `player_sum_mismatch` (any counter but `tov` that does not sum to the team
  total; `tov` may exceed by team turnovers, never fall short),
  `unknown_participation`, `played_without_seconds`.
- `start_time_et` from the schedule ("7:30p" → 19:30), `NULL` when blank;
  attendance from the box score with blank → `NULL` and 0 → 0; `venue` as
  published.
- `scraping/offline_games_backfill.py` and `nba-data backfill games --season
  <end year> [--season ...] [--output]`: reads only the cache (no client is
  constructed), selects the season's games with F8-004's selection rule, and
  writes a JSON report per season: `expected`, `loaded`, `unchanged`,
  `missing_box_score`, `quarantined` (by reason, with game ids), `warnings`,
  `players_created`, `neutral_games`, and `game_types`. It exits non-zero when
  any game is quarantined, when no game is selected, or with
  `--require-complete` when any box score is missing.
- A rerun over the same cache reports every game `unchanged` and writes
  nothing.
- `parser_contracts.py` gains `box_score` and `league_schedule` entries; lineage
  columns hold the source URL, cache path, and that version.
- Unit tests with fake parsed pages cover every gate, the Cup-final rule, the
  neutral rule (renamed arena, shared city, bubble), player creation, and
  idempotency. `tests/integration/test_game_loader_postgres.py` loads the
  committed fixture games into disposable PostgreSQL and asserts the rows, a
  rerun with no change, and a quarantined game leaving no row.
- `BUSINESS_RULES.md` documents the gates, the neutral rule, and the Cup-final
  rule; `SYSTEM_DESIGN.md` documents the command.

# Scope

`src/nba_data/scraping/loaders/games.py`, `scraping/offline_games_backfill.py`
(new); `scraping/parsers/box_score.py` (inactive names only);
`validation/parser_contracts.py`; `db/repositories/` (game upserts);
`cli/main.py` (`backfill games`); `tests/unit/`, `tests/integration/`,
`tests/fixtures/html/`; `docs/domain/BUSINESS_RULES.md`,
`docs/architecture/SYSTEM_DESIGN.md`.

# Out of scope

- Acquisition and every live request (F8-004, F8-006).
- Scheduled and postponed games, snapshots, refresh (F8-012 to F8-014, F8-008).
- Per-period scores and play-by-play (Stage 4, F8-015).
- Features and models (F8-007).
- Loading into the persistent `nba` database (F8-006).

# Impact

- **Tables:** first writes to the three F8-002 tables; new `core.players` rows
  for players with box-score lines but no player page.
- **CLI:** `backfill games`.
- **Parser:** box-score contract version bump (inactive names).

# Cross-track impact

- None beyond F8-002's handoff: the tables and their meaning are set there; this
  card fills them.

# Implementation notes

- Reuse `validation/game_pilot.py`'s reconciliation functions where they fit
  instead of writing a second copy; keep its report and tests unchanged.
- Created players have no `player_seasons`: the API's player list shows them
  with no seasons, which is true. Record it in `BUSINESS_RULES.md`.
- Known inactive-only players this must create (owner, 2026-10-24): `youngpa01`
  (2014-15), and from 2025-26 `sorbeth01` (`202510210OKC`), `batesta01`
  (`202512180DEN`), and `mangaky01` (`202512160NYK`), found by the F8-003 pilot
  rerun. They get inactive game rows with no counters, never zero-filled stats.
  After loading, `validate game-pilot` should resolve every player.
- The neutral rule needs the whole season loaded; run it as a second pass inside
  the same command and update `neutral_site` only.

# Durable knowledge updates

- `docs/domain/BUSINESS_RULES.md` — game gates, neutral-site derivation,
  Cup-final plus-minus, created players.
- `docs/architecture/SYSTEM_DESIGN.md` — `backfill games` in the offline path.

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
