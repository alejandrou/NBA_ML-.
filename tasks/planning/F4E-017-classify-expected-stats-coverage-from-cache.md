---
id: F4E-017
title: Classify expected stats coverage from the HTML cache
areas:
  - planning
  - scraping
  - data-quality
  - testing
priority: 70
depends_on:
  - F4E-013
  - F4E-014
  - F4E-022
read:
  - docs/architecture/PLAYER_PAGE_STATS_MAPPING.md
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
  - src/nba_data/scraping/parsers/player_page.py
  - src/nba_data/scraping/normalizers/player_page.py
  - src/nba_data/scraping/offline_player_stats_backfill.py
  - src/nba_data/scraping/parsers/team_season.py
validation: []
critical_actions: []
---

# Goal

Build the offline classifier that answers, for every player-season the **cache**
implies, exactly which stats rows should exist. This artifact is the sole input
to the coverage invariant in F4E-018. It reads cached HTML only and never touches
the database.

# Why this is in planning and not backlog

Three blockers, all of which must clear before this card can start.

1. **It needs a dependency that does not exist in this lifecycle yet.** The
   classifier must enumerate player pages using the *corrected* discovery
   contract from the card on the unmerged branch
   `feature/f4e-012-fix-player-page-cache-discovery-contract`. Built on today's
   discovery it would silently omit 36 players — see below — and would then
   certify their absence as correct, which is the exact failure this card exists
   to prevent. `scripts/validate_tasks.py` requires every `depends_on` to
   resolve, so the dependency cannot be declared until that card is filed.
2. **The artifact interface it shares with F4E-018 is not yet agreed.** The
   open questions are enumerated below. Starting before they are answered would
   produce an artifact F4E-018 cannot consume.
3. **Its independence from the thing it checks is not yet established.** As
   currently specified the classifier derives expectations from the same
   normalizer that produced the database, which cannot detect a defect in that
   normalizer — see *The independence problem* below. This is a design question,
   not an implementation detail, and it changes what the card builds.

# Evidence and current state

## The population is now fully explained — this corrects an earlier version of this card

An earlier revision of this card claimed **185 unclassified player-seasons** were
"the real work of this card". That was wrong, and it was wrong because the
population was decomposed but never enumerated. Checked in full against the live
`nba` database, the **634** `core.player_seasons` rows with no regular-season
aggregate stats decompose exhaustively:

| Bucket | Count | Owner |
|---|---|---|
| Season 2000, no postseason rows | 439 | F4E-013 (century rollover) |
| Players whose cached page discovery skips | **184** | the F4E-012 discovery contract |
| Postseason-only seasons, valid | **9** | none — correct as loaded |
| `jonesbo02` 2008 | 1 | F4E-014 (`5TM` marker) |
| `milleol01` 2004 | 1 | F4E-022 (placeholder counted as a team row) |
| **Total** | **634** | |

**There is no unexplained residue.** Every one of the 634 has a named cause and
an owning card.

A revision of this card between those two said **10** postseason-only seasons
were valid. That was also wrong, in a smaller and more instructive way: Oliver
Miller (`milleol01`) 2003-04 played 48 games for MIN and his cached page carries
the full row, but the season also carries a "Did not play" placeholder, and the
normalizer counts the placeholder as a second team row and rejects the season as
ambiguous. He is a dropped row wearing the costume of a valid one. The nine that
remain — `adamsja01` 2020, `hollajo02` 2016, `jeffrda01` 2023, `jonesdw02` 2013,
`lawsoty01` 2018, `mcgratr01` 2013, `thomptr01` 2023, `vildolu01` 2022,
`wrighdo01` 2016 — carry a placeholder and no real row, and are correct as
loaded. The distinction is exactly the one this classifier exists to make, so
getting it wrong here was a warning about the card's own difficulty.

## The 184: a short-surname discovery bug, measured end to end

The 184 pairs belong to exactly **36 players**, and every one of them has a
Basketball Reference id shorter than the usual nine characters:

| Id length | Players | Player-seasons |
|---|---|---|
| 6 (`qizh01`, `sypa01`) | 2 | 3 |
| 7 (`foxde01`, `gayru01`, `linje01`, `lenal01`, `roybr01`, `leeco01`, …) | 34 | 181 |

These are short surnames — Fox, Gay, Lin, Len, Roy, Lee, Acy, Bol, Joe, Key, Nix.
The cause is the discovery pattern at
[offline_player_stats_backfill.py:21](../../src/nba_data/scraping/offline_player_stats_backfill.py#L21):

```python
r"^players-(?P<initial>[a-z])-(?P<player_id>[a-z0-9]{8,10})\.html-[0-9a-f]{16}\.html\.gz$"
```

`{8,10}` excludes six- and seven-character ids. Confirmed against the cache:
**2,551 player pages are cached; 2,515 match the pattern; the 36 that do not are
exactly these 36 players.** Their pages are present and parseable — Rudy Gay's 17
seasons, De'Aaron Fox's 8, Jeremy Lin's 9 — so the data is fully recoverable and
this is omission at discovery, not a gap in the archive.

Their `core.player_seasons` rows exist because those come from **team** pages,
which discovery handles correctly. Only the player-page-fed stats are missing.
That asymmetry is precisely what F4E-018's invariant is meant to catch.

## Why expectations must come from the cache, not the database

The archive silently drops rows, so the database is the thing under test. A
classifier deriving "expected" coverage from `core.player_seasons` would declare
whatever was loaded to be correct — and would, for instance, have reported the
184 above as fully covered. The cache is the only independent authority
available offline.

## Coverage is four independent dimensions, not one mutually exclusive class

An earlier revision assigned each season exactly one of four classes. That model
is **not expressive enough for F4E-018**, and this is the second reason the card
is not ready to start. Most playoff seasons carry *both* regular-season and
postseason stats; forcing a single label means a season labelled
"regular-season present" cannot also express its expected postseason rows, so
F4E-018's separate postseason rule would have nothing to check against.

The artifact must instead record, per `(player_id, season_year)`, four
independent facts:

- expected **regular-season aggregate** tables (the subset of the 8 with real values),
- expected **postseason aggregate** tables,
- expected **team-stint** rows, enumerated as `(team_code, table)` natural keys,
- whether the season is **did-not-play**, which asserts that no stats rows should
  exist **for that season type**.

A season contributing nothing to any of the four, and not marked did-not-play, is
**unexplained** and fails.

## The did-not-play marker is season-type-scoped, and does not mean "all values None"

Two corrections here, both measured, and both of which earlier revisions of this
card got wrong.

**A placeholder row is not empty.** It normalizes to exactly one value:

```python
{'age': 'Did not play - other pro league'}
```

Across the 2,551 cached pages, **1,380 distinct `(player, season)` pairs** carry
such a row under **22 distinct reason strings**, from `other pro league` (8,946
cells) and `injury` (1,256) down to `COVID-19`, `military service`, and the bare
`Did not play -`. A classifier testing for "all values `None`" would recognize
none of them. Test for the marker, not for emptiness. F4E-022 owns the
normalizer-side predicate and this card must consume the same one rather than
write a second.

**A did-not-play marker constrains one season type only.** The nine valid
postseason-only seasons above are the proof: each has a regular-season
placeholder *and* real postseason stats, because a player can join a roster after
the trade deadline or return from injury for the playoffs. So the artifact must
record the marker per season type — a regular-season placeholder asserts that no
*regular-season* rows should exist and says nothing about postseason rows. A
single season-wide "no stats expected" flag would mark all nine as failures under
F4E-018's rule while F4E-018's own criteria require them to pass. That
contradiction is what forces the scoping.

## The independence problem

The classifier is meant to be an independent authority on what the database
should contain. As written it is not, and this is the third reason the card is
not ready.

**Common-mode failure.** Deriving expectations from normalized output means the
classifier and the loader consume the *same* normalizer. Any defect that drops a
row from the database drops it from the expectation too, and the invariant passes.
This is not hypothetical — it is precisely how `milleol01` 2004 and all 184
short-id seasons would have been certified as correctly absent. Every defect this
card exists to catch is of exactly this shape.

**Player pages cannot see the whole grain.** Regular-season team-stint rows and
roster membership come from **team** pages, not player pages. A classifier reading
only player pages cannot state expected stint coverage at all, so a third of the
dimensions above have no source. `parsers/team_season.py` is now in this card's
`read` list for that reason.

Neither problem has an obvious cheap answer, which is why they are open questions
rather than acceptance criteria. Deriving expectations from raw parsed tables
rather than normalized output buys real independence from the *selection* logic
but not from the parser; enumerating from team pages fixes the stint gap but adds
a second cache traversal and a join. The card must choose deliberately.

## The three postseason-only counterexamples, re-measured

Running `parse_player_page_postseason` + `normalize_player_page_postseason` and
the regular-season pair over the cached pages:

| Player | Season | Postseason rows | Regular-season rows |
|---|---|---|---|
| `mcgratr01` (SAS) | 2013 | **16** | 8 |
| `lawsoty01` (WAS) | 2018 | **16** | 8 |
| `thomptr01` (LAL) | 2023 | **16** | 8 |

The 16 are **8 aggregate** (`source_team_code` is `None`) plus **8 stint**, one
of each across `adj_shooting`, `advanced`, `pbp`, `per_game`, `per_minute`,
`per_poss`, `shooting`, `totals`.

The 8 regular-season rows are the placeholder, selected once per table. They are
**not** empty: each carries `{'age': 'Did not play - other pro league'}` for the
first two and `{'age': 'Did not play - unsigned'}` for `thomptr01`. They fail
integer coercion in the loader and persist nothing, which is why the database
shows zero regular-season rows for these seasons. After F4E-022 the normalizer
stops emitting them at all and the persisted outcome is unchanged — the artifact
must expect **zero** regular-season rows here either way, and must reach that
answer from the marker rather than from the coercion failure.

## The database already handles these three correctly — do not "fix" them

| Player | Season | `player_postseason_totals` | `player_season_totals` |
|---|---|---|---|
| `mcgratr01` | 2013 | 1 | 0 |
| `lawsoty01` | 2018 | 1 | 0 |
| `thomptr01` | 2023 | 1 | 0 |

They are among the 634 and are correctly loaded, which is why a raw orphan count
is not a defect count.

## What this replaces

No numeric tolerance, and specifically no "≤ 11 missing is acceptable". A count
threshold cannot distinguish a valid postseason-only season from a dropped row.
Note that a tolerance of "≤ 11 per season" would have absorbed all 184 of the
discovery-bug seasons.

# Open questions

- [ ] **Artifact location and lifecycle.** Where does the classification JSON
      live — `reports/` alongside the backfill reports, a new `artifacts/`
      directory, or a caller-supplied path with no default? Is it checked in, or
      generated on demand and git-ignored?
- [ ] **Schema and version.** The artifact needs a `schema_version` that F4E-018
      validates and refuses to read when unknown. Confirm the entry shape: the
      four dimensions above keyed by `(player_id, season_year)`, with stint keys
      as explicit `(team_code, table)` pairs.
- [ ] **Freshness.** Proposal: the artifact records a cache digest — sorted
      relative paths plus content hashes over the discovered page set — and
      records the `parser_version` strings it was built with. F4E-018 recomputes
      the digest and **fails** on mismatch rather than warning, so a stale
      artifact can never certify a stale database. Confirm this is the wanted
      strictness, and confirm the digest definition is shared with the rebuild
      diff card so both compute it identically.
- [ ] **Required or optional at the CLI.** When F4E-018 runs without an artifact,
      does `validate official-stats` fail, or emit a named "coverage not
      evaluated" issue and continue? Proposal: the latter, so existing
      invocations keep working and a missing artifact can never look like a pass.
- [ ] **Which command builds it.** Proposal: a new `validate` subcommand so the
      artifact is produced by the validation surface that consumes it, rather
      than by a backfill command. This command must be named in **F4E-018's**
      scope too, which it currently is not.
- [ ] **The F4E-012 dependency.** Confirm that this card declares `depends_on`
      the merged discovery-contract card, and that this card returns to backlog
      only after that card exists in `tasks/`.
- [ ] **Independence from the normalizer.** Does the classifier read normalized
      output, raw parsed tables, or both with a disagreement between them treated
      as an issue? Reading normalized output is the cheapest and gives the
      loader-agreement property, but it cannot catch a normalizer defect, which is
      the majority of what the audit found. Proposal: classify from **raw parsed
      tables**, and record the normalizer's own selection entries alongside as
      evidence, so a disagreement between "the page has a row" and "the normalizer
      selected nothing" becomes visible instead of cancelling out.
- [ ] **Where team-stint and roster expectations come from.** Regular-season
      stints originate on team pages, which this card does not currently read.
      Decide whether the classifier traverses the 775 cached team pages as well,
      or whether stint and roster coverage are explicitly out of scope for v1 and
      F4E-018 checks only the two aggregate dimensions. Do not leave this
      implicit: an artifact silently missing a dimension would let F4E-018 report
      full coverage over a third of the grain it claims to check.

# Acceptance criteria

- A pure, offline classifier records, for each `(player_id, season_year)` the
  cache implies, the four independent coverage dimensions above with the
  evidence that decided each.
- It has **no database access** — no session, no engine, no `DATABASE_URL`.
- It enumerates player pages via the corrected discovery contract and covers all
  **2,551** cached player pages, not 2,515. A test asserts the 36 short-id
  players are discovered, naming at least `foxde01`, `gayru01`, `qizh01`.
- "Did not play" placeholders are recognized by F4E-022's shared predicate, not
  by testing for empty values, and mark the season did-not-play **for that season
  type only**. A test covers at least three of the 22 observed reason strings,
  including the bare `Did not play -`.
- A season with both regular-season and postseason stats records **both**, not
  one label. A season with a regular-season placeholder and real postseason stats
  records did-not-play for regular season and full expected coverage for
  postseason.
- The three counterexamples above are checked-in fixtures asserting 16
  postseason rows each, split 8 aggregate / 8 stint, **and** zero expected
  regular-season rows.
- `milleol01` 2003-04 is a checked-in fixture expecting **8** regular-season
  aggregate tables, so the classifier distinguishes it from the nine genuinely
  postseason-only seasons rather than absorbing it into them.
- Unexplained seasons are enumerated individually with evidence, not counted.
- The artifact carries `schema_version`, the cache digest, and the parser
  versions, per the resolved open questions.
- Any exceptions file is schema-validated: every entry requires a non-empty
  `reason` and `evidence`, and an entry the classifier can now derive is
  reported as stale.
- A repeatable command produces the classification over the whole cache and
  writes it as JSON, so F4E-018 and the rebuild-diff card consume one artifact.

# Scope

New classification module under `src/nba_data/validation/`, its CLI entry point,
its fixtures, and its tests. The exceptions file and its schema. The cache digest
helper, if it is not already provided by the discovery-contract card.

# Out of scope

Asserting anything about the database — that is F4E-018. Repairing rows. The
century fix (F4E-013), the marker predicate (F4E-014), the placeholder predicate
(F4E-022), and the discovery contract (the F4E-012 card), all of which this card
consumes rather than implements.

**Every defect those cards own is still classified here.** `jonesbo02` 2007-08
and `milleol01` 2003-04 both expect their full 8 regular-season aggregate tables,
because this card runs *after* its dependencies and the corrected normalizer
selects those rows. An earlier revision excluded Bobby Jones from
classification; that was wrong. Excluding a season because another card owns its
root cause is exactly how a classifier certifies a missing row as correct — and
since F4E-014 and F4E-022 are `depends_on` of this card, by the time it runs
there is no defect left to exclude.

# Impact

Introduces the expected-coverage artifact that F4E-018's invariant and the
rebuild-diff card both consume. No runtime behavior, no schema, no data changes.

# Implementation notes

Depends on F4E-013, F4E-014, and F4E-022 for correctness, not for code: a
classifier built on the century-buggy `_season_end_year` would file thousands of
seasons under year 1900, one built on the enumerated marker set would misread the
`5TM` season, and one built on today's selection logic would inherit the
placeholder confusion and mis-classify `milleol01`. It depends on the
discovery-contract card for the same reason at larger scale — 184 player-seasons.

Do not settle the "classify from normalized output" question here. An earlier
revision of this card instructed exactly that, on the reasoning that the
classifier and loader should agree on what a supported row is. They should — but
agreement with the thing under test is not a virtue in an oracle, and that
instruction would have made the artifact blind to every defect the audit found.
It is now an open question above, with a proposal, and must be answered before
the card starts.

Keep the exceptions file small on purpose. Every entry is a claim that the cache
cannot answer a question; if the classifier can answer it, the entry is a bug in
the classifier. On the evidence above, the file should currently be **empty** —
all 634 have named causes.

# Durable knowledge updates

- `docs/architecture/OFFICIAL_STATS_SCHEMA.md` — record the four coverage
  dimensions as the definition of expected coverage, replacing tolerance-based
  wording.
- `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md` — record that postseason-only
  seasons are normal, that a regular-season "Did not play" placeholder does not
  imply the absence of postseason stats, and that player ids are not
  fixed-width. The placeholder's own shape is recorded by F4E-022; do not restate
  it here, and do not repeat the disproved claim that it normalizes to all-`None`
  values.

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
