---
id: F4E-019
title: Document player_name_display source semantics
areas:
  - documentation
  - data-quality
  - testing
priority: 60
depends_on: []
read:
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
  - docs/domain/BUSINESS_RULES.md
  - src/nba_data/db/models/stats.py
  - src/nba_data/scraping/loaders/team_season_stats.py
  - src/nba_data/scraping/normalizers/player_page.py
validation:
  - uv run pytest tests/unit/test_team_season_stats_loader.py tests/unit/test_player_page_stats_loader.py
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Document what `player_name_display` means, so its uniform NULL-ness across the
player-page-fed tables reads as designed behavior rather than as a bug to be
re-filed. The column stays; the defect is that nothing says what it is.

# Evidence and current state

## Where the column exists and where it is populated

Introspected from `Base.metadata`:

- **33** tables live in the `stats` schema.
- **32** of them carry `player_name_display`. The only one without it is
  `stats.player_team_season_roster`.
- The **8 regular-season team-stint** tables are populated: the team-page loaders
  map the source's `name_display` cell to the column at
  [team_season_stats.py:101 and seven sibling maps](../../src/nba_data/scraping/loaders/team_season_stats.py#L101).
- The remaining **24** — 8 regular aggregate, 8 postseason aggregate, 8
  postseason team-stint, all fed from player pages — are **never written**. No
  player-page loader references `player_name_display`.

This is not an oversight in the loader. Running the repository's own player-page
normalizer over cached pages, `player_name` is `None` on every selected row: the
player-page stats tables genuinely do not print a name cell, because the page is
already scoped to one player. The column is NULL there because the source prints
nothing there.

## The proposed meaning

> `player_name_display` is **the name as printed in this source row**. It is
> NULL where the source row prints no name. It is not the player's identity, is
> not authoritative, and must never be used to join, match, or resolve a player —
> `basketball_reference_player_id` is the identity.

## Correction to the evidence previously cited for this card

The Artest / World Peace example that motivated this card **does not hold in this
archive**, and the card must not repeat it. Measured over all 775 cached team
pages and the `artesro01` player page:

- The player-page `<h1>` renders **"Metta World Peace"**.
- Every cached team page that lists him — **including the 2004 Indiana page** —
  also renders **"Metta World Peace"**. The set of distinct renderings for
  `artesro01` across the entire cache is exactly `{"Metta World Peace"}`.

Basketball Reference renders the player's **current** name retroactively. There
is no "Ron Artest" string anywhere in the cache, so this archive contains **no
evidence of era-specific naming at all**, and cannot be used to argue for one.

Of the 2,702 players appearing on cached team pages, 207 render under more than
one string. **None of the variation is historical, but not all of it is
abbreviation.** Two distinct kinds appear:

- **Abbreviation** — `{"LeBron James", "L. James"}`,
  `{"Victor Wembanyama", "V. Wembanyama"}`. The same name, shortened to fit a
  narrow column.
- **Spelling and transliteration** — `{"Efthimios Rentzias",
  "Efthimi Rentzias"}`. Neither string is an abbreviation of the other; they are
  two renderings of a name that has no single canonical Latin spelling.

The distinction matters to the definition below. "Abbreviation" implies a
mechanical, reversible shortening that a consumer could undo; a transliteration
variant is not recoverable from the other form. Both are covered by *the name as
printed in this source row*, and neither is a historical name — which is the
point — but the card must not describe the second as the first.

# Human decisions or resources

- [x] Keep `player_name_display` on all 32 tables, uniform and nullable.
      Dropping it would be a 32-table migration for no functional gain, and the
      uniform stats-table shape is itself relied on by `STATS_TABLE_SPECS` in
      [official_stats.py:131](../../src/nba_data/validation/official_stats.py#L131).
- [x] Document it in `docs/architecture/OFFICIAL_STATS_SCHEMA.md` as internal
      source semantics, **not** in `docs/architecture/API_CONTRACT.md` — whether
      the API exposes the field at all is F6-004's decision, and stating it in
      the contract would pre-empt that card.

# Acceptance criteria

- `OFFICIAL_STATS_SCHEMA.md` states the meaning above, records that 8 tables are
  populated from team pages and 24 are NULL by design because the player-page
  source prints no name cell, and names `player_team_season_roster` as the one
  stats table without the column.
- It records the measured naming evidence: Basketball Reference renders current
  names retroactively; the archive contains no era-specific names; the observed
  multi-rendering cases are **abbreviations and spelling variants**, with one
  worked example of each, and neither is reversible into a canonical form.
- A test asserts that the player-page loaders do **not** synthesize
  `player_name_display` — neither from the page `<h1>`, nor from
  `core.players.full_name`, nor from the player id.
- A test asserts the team-page loaders still populate it from the source
  `name_display` cell.
- No migration, no schema change, no data change.

# Scope

- `docs/architecture/OFFICIAL_STATS_SCHEMA.md` — the definition and the
  population split.
- `docs/domain/BUSINESS_RULES.md` — the retroactive-naming finding. This is
  listed under durable knowledge updates below, so it is in scope; an earlier
  revision omitted it here, which would have left the card unable to deliver its
  own stated output.
- `tests/unit/` — the two loader assertions.

No production code changes are expected; if a loader is found synthesizing the
value, removing that synthesis is in scope.

# Out of scope

Dropping or renaming the column. Deciding what `core.players.full_name` means,
which is F4E-021. Deciding whether the API exposes the field, which is F6-004.
Backfilling the column into the 24 player-page tables.

# Impact

Documentation and tests only. Fixes the recurring misreading that the NULL
column is a data defect, and gives F6-004 a stated source semantic to decide
against.

# Implementation notes

This card exists so the question is not re-filed. Write the meaning as a
definition with its evidence, not as a note.

Do not cite the Artest example. It was measured and disproved; citing it would
reintroduce the error this card corrects.

# Durable knowledge updates

- `docs/architecture/OFFICIAL_STATS_SCHEMA.md` — the `player_name_display`
  definition, the 8/24 population split, and the retroactive-naming finding.
- `docs/domain/BUSINESS_RULES.md` — record that Basketball Reference renders
  current player names retroactively, so no source in this archive carries an
  era-specific name.

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
