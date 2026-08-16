---
id: F4E-017
title: Build a cache-derived official-stats coverage artifact
areas:
  - scraping
  - data-quality
  - testing
  - documentation
priority: 70
depends_on:
  - F4E-012
  - F4E-013
  - F4E-014
  - F4E-022
  - F4E-025
read:
  - docs/architecture/PLAYER_PAGE_STATS_MAPPING.md
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
  - src/nba_data/scraping/cache_inventory.py
  - src/nba_data/scraping/parsers/player_page.py
  - src/nba_data/scraping/parsers/team_season.py
  - src/nba_data/scraping/normalizers/player_page.py
  - src/nba_data/scraping/normalizers/team_season.py
  - src/nba_data/scraping/offline_player_stats_backfill.py
validation:
  - uv run pytest tests/unit
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Build a deterministic, database-free JSON artifact that states the exact
official-stats natural keys implied by the cached team-season and player pages.
F4E-018 will compare this independent expectation set with PostgreSQL.

# Evidence and current state

The current official-stats validator checks schema shape, grains, numeric
ranges, source metadata, and report totals. It cannot answer whether a specific
player-season row that should exist is absent. The archive audit found several
such omissions even though aggregate report totals reconciled.

One cache source is insufficient:

- player pages are authoritative for regular aggregate, postseason aggregate,
  and postseason team-stint rows;
- team-season pages are authoritative for regular roster and team-stint rows.

The artifact therefore traverses both cache families. It derives expectations
from parsed source rows and small source-semantic predicates, not from persisted
rows or from the same normalizer selection result the loaders consume. Reusing
normalizer output as the oracle would make a normalizer defect disappear from
both the database and the expectation set.

The prerequisite fixes are explicit dependencies. F4E-012 supplies complete
player-page discovery, F4E-013 supplies correct season-year rollover, F4E-014
supplies the open-ended multi-team rule, F4E-022 supplies the did-not-play
predicate, and F4E-025 supplies the parser-contract registry recorded in the
artifact.

# Resolved artifact contract

- The artifact is generated on demand and is not committed. The build command
  requires an explicit `--output PATH`; callers will normally choose `reports/`,
  which is already ignored.
- Schema version 1 is a top-level integer and unknown versions are rejected.
- Entries use natural keys, never surrogate database IDs.
- Each `(basketball_reference_player_id, season_year)` entry has independent
  sets for regular aggregate tables, postseason aggregate tables, regular
  team-stint keys, and postseason team-stint keys. A team-stint key is
  `(team_code, table)`; the regular set may include roster.
- Did-not-play evidence is recorded separately for regular season and
  postseason. It suppresses only the matching aggregate expectation. It does
  not erase independently observed roster or team-stint expectations.
- The artifact records the current parser-contract identifiers from F4E-025.
- The cache fingerprint is SHA-256 over a canonical stream of each discovered
  source's cache-root-relative POSIX path and SHA-256 of its decompressed HTML,
  sorted by path. It records player-page and team-page counts separately.
- Any parsed season that produces no expectation and has no did-not-play
  explanation is written under `unexplained`; the build command writes the
  artifact and exits non-zero.

# Human decisions or resources

- None.

# Acceptance criteria

- A pure module under `src/nba_data/validation/` builds schema-version-1 coverage
  artifacts without importing database sessions, engines, ORM models, or HTTP
  clients.
- `uv run nba-data validate build-stats-coverage --output PATH` builds the
  artifact from `Settings.scraper_cache_dir`. It supports an explicit cache-root
  override for offline fixtures and refuses a missing root.
- Player pages are enumerated through the corrected shared discovery contract;
  team pages use the strict cache inventory contract. Unreadable, empty, or
  malformed candidates are reported and make the build fail.
- Expectations are classified from parsed source rows. Normalizer selection
  entries may be recorded as comparison evidence, but they are not the source
  of the expected key set; a disagreement is reported rather than cancelled.
- Regular aggregate selection follows the official single-team/multi-team rule,
  including any numeric marker of at least `2TM`. `TOT` never becomes an
  expectation.
- Regular roster and team-stint expectations come from team-season pages.
  Postseason aggregate and team-stint expectations come from player pages.
- F4E-022's shared did-not-play predicate is reused. Tests cover at least three
  observed reason strings, including the bare `Did not play -`, and prove the
  marker is season-type scoped.
- Tests prove a player-season can simultaneously carry regular and postseason
  expectations, and that a regular did-not-play marker can coexist with real
  postseason expectations.
- Fixture coverage includes a short player ID, a century-crossing season,
  `5TM`, `milleol01`-shaped real-row-plus-placeholder input, a traded regular
  season, and postseason team stints.
- Reordering source files or JSON entries does not change the fingerprint or
  semantic artifact. Changing a relative path or decompressed HTML does.
- Tests use checked-in miniature HTML fixtures only. They do not read the real
  `data/` directory, connect to PostgreSQL, or make network requests.

# Scope

- A coverage artifact builder and typed schema under `src/nba_data/validation/`.
- A `validate build-stats-coverage` CLI command.
- Cache enumeration/fingerprint helpers where needed.
- Offline fixtures, unit tests, and the two official-stats mapping documents.

# Out of scope

Reading or validating PostgreSQL, which is F4E-018. Repairing any row. Running a
backfill or acquisition. Creating a checked-in full-archive artifact or an
exceptions allowlist.

# Impact

Introduces the independent oracle consumed by F4E-018. It is cache-only and
read-only; no database schema, persisted data, scraper rate limit, or runtime API
behavior changes.

# Implementation notes

Keep the source-semantic classifier small and explicit. Sharing stable semantic
predicates such as `is_multi_team_marker` and F4E-022's did-not-play detector is
correct; sharing the normalizer's final row-selection result is not.

Write the JSON atomically after successful serialization. On classification
issues, preserve the diagnostic artifact but return a non-zero command exit so
automation cannot mistake it for a complete oracle.

# Durable knowledge updates

- `docs/architecture/OFFICIAL_STATS_SCHEMA.md` — define cache-derived natural-key
  coverage and identify the two cache sources.
- `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md` — record season-type-scoped
  did-not-play behavior and the player-page portions of the artifact.

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
