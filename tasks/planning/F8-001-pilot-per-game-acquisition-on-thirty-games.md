---
id: F8-001
title: Pilot per-game acquisition on thirty games
track: data
areas:
  - planning
  - scraping
  - data-quality
  - testing
  - documentation
priority: 100
depends_on: []
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/decisions/0003-cache-raw-html.md
  - docs/decisions/0004-rate-limited-scraping.md
  - docs/decisions/0016-live-vs-offline-validation.md
  - docs/validation/PLAYER_PAGE_CACHE_ACQUISITION.md
  - src/nba_data/scraping/client.py
  - src/nba_data/scraping/cache.py
  - src/nba_data/scraping/player_page_acquisition.py
  - src/nba_data/scraping/nba_team_season_manifest.py
  - src/nba_data/config/settings.py
  - src/nba_data/cli/main.py
validation: []
critical_actions:
  - Live acquisition of about thirty games (schedule, box score, play-by-play) from the chosen provider, under an approved manifest and the owner's direct instruction.
---

# Goal

Stage 1 of `docs/ml/PREDICTOR_PLAN.md`: prove, on thirty games, that per-game
data (schedule, final result, team and player box score, play-by-play) can be
acquired, cached, parsed offline, and reconciled — before any schema is written
or any large acquisition is planned. The deliverable is a measured go/no-go
report, not a dataset.

# Evidence and current state

- There is no per-game data anywhere: `alembic/versions/` ends at
  `0008_drop_raw_schema`, and no model in `src/nba_data/db/models/` has a game
  grain. The `stats.*_pbp` tables are season summaries.
- Every acquisition path is bound to Basketball Reference:
  - `scraping/client.py:38` — `BasketballReferenceClient`, the one HTTP client,
    with 429/5xx handling and the cache.
  - `config/settings.py:9,29-30,43-49` — the 6-second floor
    (`MINIMUM_SCRAPER_DELAY_SECONDS`) and the 10/min default (≤20), validated
    with a message naming Basketball Reference.
  - Host checks reject anything but `basketball-reference.com`:
    `scraping/team_season_pages.py:141`, `scraping/backfill_manifest.py:404`,
    `scraping/offline_processor.py:350`.
  - `cli/main.py:675-690,766-801` — the `--owner-approved` +
    `--execute-approved-manifest` gate, per acquisition command.
  - `scraping/cache.py:128` — host-directory mapping already falls back to a
    safe per-host directory for other hosts, so a second provider fits the cache
    layout.
- `httpx` is already a runtime dependency (`pyproject.toml`); `nba_api` and
  `pbpstats` are not.
- `tasks/manifests/F4B-LIVE-001-pilot-team-season-20260525.json` is the
  precedent for an approved pilot manifest.

# Human decisions or resources

- [ ] **Provider.** NBA.com (stats V3 endpoints and/or `cdn.nba.com` JSON) as
      the plan proposes, or Basketball Reference box-score and play-by-play
      pages (existing infrastructure, slower at 6 s/request)? For NBA.com:
      confirm you accept its terms of use for local, non-commercial use.
- [ ] **Client.** Plain `httpx` against the endpoints (no dependency change) or
      `nba_api` (a `shared` card for `pyproject.toml`/`uv.lock` first, which
      blocks both tracks)?
- [ ] **Per-provider limits** for a non-Basketball-Reference host. Proposal:
      same 6 s floor, 10/min default, stop on 429, honor `Retry-After`.
- [ ] **Pilot content.** Schedule + box score + play-by-play for all thirty, as
      the plan says, or box score only first?
- [ ] **Game selection.** Approve the thirty-game list (seasons and edge cases:
      overtime, simultaneous substitutions, score reviews, incomplete data)
      once drafted as a manifest.

# Acceptance criteria

To be sharpened by `prepare-task`. In outline:

- A provider client that reuses the cache, provenance metadata, rate limiting,
  and 429 handling, with its own host allow-list — Basketball Reference paths
  unchanged.
- The approval gate extended to the new acquisition command: refuses without
  `--owner-approved` and an approved manifest; tests prove the refusal.
- An approved manifest in `tasks/manifests/` listing the thirty games.
- Offline parsers for the acquired documents, tested against cached fixtures.
- A pilot report in `docs/validation/` with, per game: identity resolution
  (teams, players), final score vs box score vs events reconciliation, requests,
  bytes, wall time, and `pbpstats` compatibility if play-by-play is in scope —
  ending in an explicit go/no-go and the recommended endpoint.
- No database writes and no schema change.

# Scope

`src/nba_data/scraping/` (new provider client, manifest, parsers),
`src/nba_data/config/settings.py` (per-provider limits), `src/nba_data/cli/`
(new gated command), `tasks/manifests/`, `tests/unit/`, `tests/fixtures/`,
`docs/validation/`.

# Out of scope

Tables and migrations (`F8-002`). Acquisition beyond the thirty games. Any
model training. Changing the Basketball Reference limits or gate.

# Impact

- **Scraping:** a second provider, cache directory, and gated CLI command.
- **Config:** per-provider rate-limit settings.
- **Data:** cache files only; the database is untouched.

# Cross-track impact

- None.

# Implementation notes

- Proposed split, to confirm in `prepare-task`: (1) provider client, limits, and
  gate with offline tests; (2) manifest and the live pilot run; (3) parsers and
  the pilot report. The live run is the only critical action.
- If the owner picks `nba_api`, a `shared` dependency card must merge first.
- Generalizing the gate must keep every existing Basketball Reference guard and
  its tests intact (AGENTS.md, "Live-scraping approval gate").

# Durable knowledge updates

- `docs/ml/PREDICTOR_PLAN.md` — record the chosen provider and endpoint.
- `docs/decisions/` — a new ADR for adding a second data provider.

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
