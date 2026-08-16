---
id: F4E-024
title: Recover player seasons lost to the multi-team marker enumeration
areas:
  - scraping
  - data-quality
  - operations
priority: 60
depends_on:
  - F4E-014
read:
  - docs/decisions/0007-handle-tot-and-trades.md
  - docs/architecture/PLAYER_PAGE_STATS_MAPPING.md
  - src/nba_data/scraping/offline_player_stats_backfill.py
  - src/nba_data/scraping/offline_player_postseason_stats_backfill.py
  - src/nba_data/scraping/normalizers/player_page.py
  - tasks/backlog/F4E-022-stop-treating-did-not-play-placeholders-as-team-rows.md
validation: []
critical_actions:
  - Running a backfill against the persistent database is a write to real data and requires explicit owner approval naming the operation and its scope.
  - Deciding to re-run the whole archive rather than a targeted repair changes the blast radius and is the owner's call, not the card's.
---

# Goal

Decide how the seasons that F4E-014 unblocked at the parser actually reach the
database, and then carry that out. F4E-014 fixed what the parser *produces*; it
deliberately wrote nothing. Until a backfill runs, Bobby Jones (`jonesbo02`)
2007-08 is still an empty season in `stats.player_season_*`, and the rows already
there are still stamped with the parser versions that produced them.

# Evidence and current state

## What F4E-014 changed, and what it did not

F4E-014 replaced three hard-coded `{2TM, 3TM, 4TM}` enumerations with a semantic
predicate in `src/nba_data/domain/team_codes.py`, and bumped both player-page
parser versions to `-v3`. The regression test proves the effect at the
normalizer: the `5TM` season selects **8** aggregate rows where it previously
selected **0**.

Nothing re-reads the cache on its own. A parser-version bump is a *label* on
rows written from that point forward — it does not re-label or re-derive
anything already persisted. So the defect is fixed in code and still present in
data.

## What is actually missing

From the archive audit, the marker census across 2,551 cached player pages:

| Marker | Player-seasons | Rows |
|---|---|---|
| `2TM` | 1,695 | 13,402 |
| `3TM` | 110 | 870 |
| `4TM` | 4 | 30 |
| `5TM` | 1 | 8 |

Only the `5TM` season fell outside the old enumeration, so the **known** loss is
one player-season. That number should be re-derived, not trusted: it predates
this card, and F4E-014 explicitly did not re-scan the cache.

## The interaction with F4E-022

F4E-022 ("Stop treating Did not play placeholders as team rows") is already in
`tasks/backlog/` and depends on F4E-014. It touches the same function
(`_select_full_season_row`), affects far more seasons (1,380 `(player, season)`
pairs carry a DNP placeholder), and will bump the parser version again — to
`-v4`.

That makes the sequencing the central question. A cache-only backfill over 2,551
pages is not free, and running one now and another after F4E-022 does the work
twice for a one-season gain.

# Human decisions or resources

- [ ] **1. Targeted repair now, or one broad backfill after F4E-022?** A
      targeted `jonesbo02` / 2008 repair under `-v3` fixes the one known loss
      immediately and touches almost nothing. Waiting for F4E-022 and running
      one cache-only backfill under `-v4` costs a single pass instead of two,
      but leaves the season empty until then. Both are defensible; the
      difference is whether the empty season matters before F4E-022 lands.
- [ ] **2. Is a re-measurement required first?** The census above is inherited.
      Confirming it means re-scanning the cache read-only, which is safe and
      needs no approval — but it is a real cost and may not change the decision.
- [ ] **3. What happens to rows still stamped `-v1` and `-v2` that a backfill
      would not otherwise touch?** Leaving them means the table holds three
      parser generations with no way to tell from a row which contract is
      current. This is the question F4E-025 exists to answer; decide here
      whether that answer blocks this card or merely follows it.
- [ ] **4. Which database, and with what authorization?** A backfill against the
      persistent `nba` database is a write to real data. The owner must name the
      operation and its scope. Rehearsing on a disposable database first is
      free and is probably the right default.

# Acceptance criteria

To be finalised once the decisions above are made. At minimum:

- The `5TM` season is no longer empty in `stats.player_season_*`, verified by
  querying the grain rather than by reading a report.
- The number of player-seasons repaired is stated as a measured figure, and
  matches a re-derived count from the cache.
- No row is written outside the scope the owner authorized, and the run is
  reproducible from the report it emits.
- Whatever is decided about `-v1`/`-v2` rows is written down in a durable
  document, not only in this card.

# Scope

To be finalised.

# Out of scope

- Changing the marker rule itself. F4E-014 owns it and it is settled.
- Live scraping. This is a cache-only operation; contacting Basketball Reference
  is a separate authorization and is not needed to recover these rows.

# Impact

To be finalised.

# Implementation notes

To be finalised.

# Durable knowledge updates

- `docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md` — row DB-02 currently
  reads "fixed at the parser; persisted rows not yet repaired". This card is
  what changes that.

# Review evidence

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
