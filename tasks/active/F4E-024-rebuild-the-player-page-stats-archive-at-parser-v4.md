---
id: F4E-024
title: Rebuild the player-page stats archive at parser v4
areas:
  - scraping
  - data-quality
  - operations
  - documentation
priority: 60
depends_on:
  - F4E-014
  - F4E-022
  - F4E-025
read:
  - docs/validation/OFFLINE_DATABASE_PREPARATION.md
  - docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md
  - docs/architecture/PLAYER_PAGE_STATS_MAPPING.md
  - src/nba_data/validation/parser_contracts.py
  - src/nba_data/scraping/offline_player_stats_backfill.py
  - src/nba_data/scraping/offline_player_postseason_stats_backfill.py
  - src/nba_data/db/repositories/stats.py
  - scripts/validate_postgres_local.py
validation:
  - uv run ruff check .
  - uv run pytest
  - uv run python scripts/validate_tasks.py
  - bash scripts/validate_database.sh
critical_actions:
  - This card rehearses on a scratch database it creates and drops. It does NOT authorize any write to the persistent `nba` database. The owner authorized the rehearsal only (2026-08-26); the production run needs a separate, direct instruction naming the operation and its scope.
  - Every command in this card is cache-only. Contacting Basketball Reference is a separate authorization and is not needed to recover any of these rows.
  - The scratch database name must be verified to differ from the configured `nba` database before any backfill runs, the way `scripts/validate_postgres_local.py` already asserts it.
---

# Goal

Rebuild `stats.player_season_*`, `stats.player_postseason_*` and
`stats.player_team_postseason_*` from the cached archive under the current
parser contract (`-v4`), rehearsed end to end on a scratch database, and prove by
grain query that the rebuild recovers the player-seasons three separate parser
fixes unblocked and leaves nothing stale behind.

The card that reached `tasks/planning/` framed this as recovering **one**
player-season lost to the multi-team marker enumeration. Measured against the
live database, that framing was wrong in both directions: the marker season is
one of **625** recoverable player-seasons, and every player-page row in the
database is stamped `player-page-parser-v1` — three generations behind the
parser, and a hard validation failure since F4E-025.

The owner's decisions on 2026-08-26 settle the scope and the authorization. This
card carries them out; it no longer decides anything.

# Evidence and current state

## The persistent database is uniformly `v1`

The planning card assumed a mix of `-v1`, `-v2` and `-v3` rows and asked what to
do about the stragglers. Queried against the running `nba_postgres` container,
there is no mix:

| Table group | `parser_version` | Rows |
|---|---|---|
| all 8 `stats.player_season_*` | `player-page-parser-v1` | 12,042 each — **96,336** |
| all 8 `stats.player_postseason_*` | `player-page-postseason-parser-v1` | 5,066 each — **40,528** |
| all 8 `stats.player_team_postseason_*` | `player-page-postseason-parser-v1` | 5,066 each — **40,528** |
| the 9 `stats.player_team_season_*` | `team-season-parser-v1` | 14,332 / 129,000 total |

`select distinct parser_version` returns exactly one value per producer. **No
`-v2` or `-v3` row exists anywhere.** Those generations were bumped in code
(F4E-013, F4E-014) and never written to this database, because neither card ran
a backfill — both said so explicitly.

That deletes decision 3 from the planning card as posed. There is no mixed-
generation table to reason about; there is one generation, and it is the oldest
one.

## Every player-page row currently fails validation

F4E-025 landed and made lineage an enforced contract, not a label.
[`parser_contracts.py`](../../src/nba_data/validation/parser_contracts.py) marks
`player-page-parser-v4` and `player-page-postseason-parser-v4` as the only
current player-page identifiers, and
[`official_stats.py:1197-1206`](../../src/nba_data/validation/official_stats.py#L1197-L1206)
raises `stale_parser_version` for any known-but-not-current value, counted into
`parser_lineage_violations` and folded into `passed = not issues`.

So all **177,392** player-page rows in `nba` are a validation failure today. A
targeted single-season repair would have fixed one season and left every one of
them failing — which is why the owner chose the full rebuild.

## What the rebuild actually recovers

`core.player_seasons` holds 12,676 rows; only 12,042 have regular-season
aggregate stats. The 634-row gap is already decomposed, verified, and recorded
in [`ARCHIVE_DATA_AUDIT_DISPOSITION.md:89-99`](../../docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md#L89-L99)
— "fully, with no residue":

| Bucket | Count | Cause | Fixed by | Generation |
|---|---|---|---|---|
| Season 2000 | 439 | `1999-00` century rollover to 1900 | F4E-013 | `-v2` |
| 36 players with 6- or 7-character ids | 184 | player-page discovery pattern | F4E-012 | discovery, not parser |
| `jonesbo02` 2008 | 1 | `5TM` marker outside `{2TM,3TM,4TM}` | F4E-014 | `-v3` |
| `milleol01` 2004 | 1 | DNP placeholder counted as a real team row | F4E-022 | `-v4` |
| Postseason-only seasons | 9 | **none — correct as loaded** | — | — |
| **Total** | **634** | | | |

All four defects are fixed in code and none has ever been written to the
database. The rebuild is therefore expected to recover **625** player-seasons —
12,042 + 625 = **12,667** — with the 9 postseason-only seasons correctly staying
empty. That is arithmetic over DB-verified figures, so the card treats it as a
prediction to be confirmed, not a result.

The marker season this card was originally named for is the single `1` in row
three.

## Confirming the marker census, read-only

Planning decision 2 asked whether the inherited marker census needed
re-measuring. It did not need owner input — re-scanning the cache is read-only
and safe — so it was simply done rather than left as a question. Driving the
repository's own `parse_player_page_*` and `is_multi_team_marker` over all 2,551
cached pages, across both the regular-season and postseason table sets, with
**0 parse failures**:

| Marker | Player-seasons | Rows |
|---|---|---|
| `2TM` | 1,695 | 13,402 |
| `3TM` | 110 | 870 |
| `4TM` | 4 | 30 |
| `5TM` | **1** | **8** |
| **Total** | **1,810** | **14,310** |

**The inherited census reproduces exactly** — every figure matches the number
the planning card carried, so nothing downstream of it needs revisiting. The
re-derivation also enumerates, rather than merely counts, the player-seasons
whose marker fell outside the old `{2TM, 3TM, 4TM}` enumeration. There is
exactly one, and it is the season the card was named for:

```text
regular  jonesbo02  2008
```

No postseason player-season carries a marker outside the old enumeration, so the
marker defect costs one regular-season aggregate row per supported table — 8
rows — and nothing else.

One limit worth stating rather than hiding: this measurement is faithful for the
**marker** rule only. Reproducing the pre-F4E-022 selection would need the old
code's *missing* `is not None` guard on the team code, which is what let a DNP
placeholder count as a real team row; a re-implementation built from the current
predicate cannot express that bug. F4E-022's own figures stand for the DNP
dimension, and the coverage artifact is the oracle for both.

Discovery enumerated **2,551** cached player pages, matching
`find data/raw/html -name 'players-*.html.gz' | wc -l` exactly, so the F4E-012
discovery omission that cost 184 player-seasons is closed at the enumeration
boundary as well as in code.

## The upsert-only risk, and why it is checkable rather than arguable

[`StatsRepository`](../../src/nba_data/db/repositories/stats.py) exposes only
`upsert_*` methods. There is no delete anywhere in the stats write path. A
re-run therefore **updates** rows the new parser still selects, **inserts** the
recoveries, and **cannot remove** a row the new parser no longer produces.

Read from the source evidence, no such row should exist: the DNP-only seasons
that `-v1` mis-selected emitted values like `Did not play - other pro league`
into integer columns, so the loader rejected all of them
(`ValueError`, 577 failed entries), and the century-rollover rows resolved to
season 1900, which is not in `core.seasons` (range 2000–2025), so they were
never written either. Both failure modes dropped rows rather than persisting bad
ones.

That is reasoning, and this card does not ship reasoning as a result. F4E-018
already built the mechanism that settles it by measurement:
`validate official-stats --coverage-artifact` reports
`coverage_unexpected_<dimension>_row` for any natural key present in `stats.*`
that the cache-derived oracle does not expect. A clean rebuild with zero
`coverage_unexpected_*` findings **is** the proof that upsert-only left no
residue. If findings appear, the card has found a real defect and stops.

## The persistent database is a migration behind

`nba` reports `alembic_version = 0006_synthetic_team_codes`; the head in
[`alembic/versions/`](../../alembic/versions/) is `0007_team_bref_id_not_null`.
The rehearsal runs at head. This gap belongs in the handover procedure as a
preflight step, not in a footnote — it is exactly the kind of difference that
makes a rehearsal's numbers fail to reproduce.

F4E-020 and F4E-021 will add `0008` and `0009`. Neither touches a `stats` table,
so neither changes this rebuild; but if either lands first, the rehearsal must be
re-run at the new head before the production procedure is trusted.

## Documentation that the rebuild falsifies

- [`OFFLINE_DATABASE_PREPARATION.md:194-202`](../../docs/validation/OFFLINE_DATABASE_PREPARATION.md#L194-L202)
  states the Phase 4E baseline as 96,336 regular player rows and 306,392 total,
  and says the player-stats producer "currently exits nonzero until the
  placeholder-row fix in F4E-022 is applied." F4E-022 **is** applied; the
  sentence is stale, and the totals change with the rebuild.
- [`ARCHIVE_DATA_AUDIT_DISPOSITION.md:37`](../../docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md#L37)
  row DB-02 still reads "fixed at the parser; persisted rows not yet repaired".

# Human decisions or resources

- [x] **1. Targeted repair, or a full rebuild?** **Full rebuild at `-v4`**,
      re-running both player-page backfills over all 2,551 cached pages. The
      planning card offered "targeted `jonesbo02` repair now" versus "one broad
      backfill after F4E-022", but F4E-022 and F4E-025 both landed before this
      card was prepared, which removed the sequencing question and added a
      decisive one: the targeted repair leaves 177,392 rows stamped `-v1`, every
      one of them a `stale_parser_version` failure, and leaves 624 other
      player-seasons empty. The card is retitled accordingly; the `5TM` season
      becomes one line item in a larger recovery. (Owner, 2026-08-26.)
- [x] **2. Is a re-measurement required first?** **Done, not deferred.**
      Re-scanning the cache is read-only and needed no approval, so it was
      carried out during preparation rather than left as a question. The census
      is recorded above and re-derived from the repository's own parser, not
      inherited. (Resolved during preparation, 2026-08-26.)
- [x] **3. What happens to rows still stamped `-v1`/`-v2`?** **Nothing is left
      behind, because the rebuild replaces the whole player-page archive.**
      There are no `-v2` or `-v3` rows to strand, and every `-v1` row is
      re-stamped in place by the upsert. F4E-025 already decided the policy —
      stale lineage fails validation — so the question this card inherited is
      answered by an exit code rather than by a document. The residue question
      that *is* live (rows the new parser no longer produces) is settled by the
      F4E-018 coverage comparison, not by argument. (Owner, 2026-08-26.)
- [x] **4. Which database, and with what authorization?** **A scratch database
      only.** The card creates one, migrates it to head, rebuilds into it,
      validates it, and drops it. Writing to the persistent `nba` database is
      **not** authorized by this card and must not happen inside it. The card's
      deliverable for production is a written, preflighted procedure the owner
      can execute later on a separate, direct instruction. (Owner, 2026-08-26.)

# Acceptance criteria

## Isolation

- The rehearsal runs against a uniquely named scratch database on the same
  PostgreSQL server, created by this card and dropped in a `finally` path
  whatever the outcome, following the pattern already established in
  [`scripts/validate_postgres_local.py`](../../scripts/validate_postgres_local.py):
  generate the name, assert it does not collide with the configured database,
  point a child process at it via `DATABASE_URL`, drop it at the end.
- `nba` is untouched. Proven, not asserted: capture
  `select parser_version, count(*)` across the player-page stats tables of `nba`
  before and after the rehearsal and show the two captures are byte-identical.
- No command in the card passes `--execute-approved-*` while `DATABASE_URL`
  resolves to the configured `nba` database.

## The rebuild

- The scratch database is migrated to head (`0007_team_bref_id_not_null`) and
  `uv run alembic check` is clean before any backfill runs.
- `backfill offline`, `backfill stats`, `backfill player-stats` and
  `backfill player-postseason-stats` run in that order, cache-only, each writing
  its JSON report under `reports/`.
- `backfill player-stats` reports **0 entries with `status="failed"`**. F4E-022
  predicted this at the normalizer level and deliberately did not run a backfill
  to confirm it; this card is the first run that can, and the figure is reported
  as measured.
- Core counts in the scratch database match the Phase 4D baseline exactly —
  `core.players` 2,551, `core.player_seasons` 12,676,
  `core.player_team_seasons` 14,344 — confirming the rebuild starts from the same
  core the current archive has, so any stats difference is attributable to the
  parser and nothing else.

## The recovery, measured at the grain

- `select count(distinct player_season_id) from stats.player_season_totals`
  returns **12,667**, up from 12,042. If it does not, the difference is
  enumerated player-season by player-season and explained before the card leaves
  review — a near-miss is not accepted as a rounding matter.
- The recovery reconciles against the audit's decomposition: 439 season-2000
  rows, 184 short-id rows, `jonesbo02` 2008, and `milleol01` 2004, summing to
  625. Each bucket is counted separately, not inferred from the total.
- `jonesbo02` 2008 has **8** regular-season aggregate rows, verified by a query
  joining `core.players` and `core.seasons` on the grain, not by reading a
  report.
- `milleol01` 2004 has **8** regular-season aggregate rows whose values include
  `games = 48` and `pts = 121`, so a placeholder can never satisfy the check.
- The **9** postseason-only seasons — `adamsja01` 2020, `hollajo02` 2016,
  `jeffrda01` 2023, `jonesdw02` 2013, `lawsoty01` 2018, `mcgratr01` 2013,
  `thomptr01` 2023, `vildolu01` 2022, `wrighdo01` 2016 — still have **0**
  regular-season aggregate rows and their postseason rows intact. They are
  correct as loaded and must not be "recovered".
- Postseason and team-stint totals are recorded **as measured**. This card does
  not predict them: F4E-013 and F4E-022 both affect postseason selection, and no
  existing document decomposes the postseason gap the way the audit decomposes
  the regular-season one. The coverage artifact is the oracle for whether the
  measured numbers are right.

## Lineage

- `select distinct parser_version` across all 33 `stats` tables in the scratch
  database returns exactly three values: `team-season-parser-v1`,
  `player-page-parser-v4`, `player-page-postseason-parser-v4`. Zero rows carry
  `-v1`, `-v2` or `-v3` player-page lineage.

## Validation

- `validate build-stats-coverage` writes the artifact and exits 0 — no
  unclassified season, no unreadable cached source.
- `validate official-stats` with all three producer reports plus
  `--coverage-artifact` and `--coverage-cache-root` exits **0** against the
  scratch database, with:
  - zero `stale_parser_version` and zero `unknown_parser_version` findings, and
    `parser_lineage_violations` at 0;
  - zero `coverage_missing_<dimension>_row` findings across all four dimensions;
  - **zero `coverage_unexpected_<dimension>_row` findings** — the measured proof
    that the upsert-only write path left no row the current parser would not
    produce;
  - `coverage_summary.freshness_status` reporting `verified`, not `unverified`.
- Any nonzero finding in the residue check stops the card rather than being
  waived: it would mean the rebuild needs a delete step, which is a different
  card with a different blast radius.

## Handover

- A written procedure for the persistent `nba` run exists in
  `docs/validation/OFFLINE_DATABASE_PREPARATION.md`, reproducible from the
  rehearsal, and including as an explicit preflight that `nba` is at
  `0006_synthetic_team_codes` while head is `0007_team_bref_id_not_null`.
- The procedure states plainly that it requires the owner's direct, current
  instruction and that this card does not supply it.

## Housekeeping

- `uv run ruff check .`, `uv run pytest`,
  `uv run python scripts/validate_tasks.py` and `bash scripts/validate_database.sh`
  all pass.

# Scope

- `docs/validation/OFFLINE_DATABASE_PREPARATION.md` — corrected baselines, the
  rebuild runbook, and the persistent-`nba` handover procedure.
- `docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md` — the DB-02 status and the
  verified-figures table.
- `reports/` — rehearsal reports and the coverage artifact. Git-ignored; keep
  them local.
- A throwaway rehearsal script under `scripts/dev/` **only if** the sequence
  cannot be driven from documented CLI commands alone. Prefer the documented
  commands: a runbook that only works through a bespoke script is not a runbook.

This card writes **no application code**. Every capability it needs already
exists — the backfills, the coverage builder, the lineage registry and the
coverage comparison all landed in F4E-014, F4E-017, F4E-018, F4E-022 and
F4E-025. If implementation finds itself editing `src/`, that is a signal to stop
and re-scope, not to proceed.

# Out of scope

- **Any write to the persistent `nba` database.** The owner authorized the
  rehearsal only.
- Live scraping. Cache-only, as every backfill command in this repository is.
- Changing the marker rule (F4E-014 owns it and it is settled), the century rule
  (F4E-013), the DNP predicate (F4E-022), or the lineage registry (F4E-025).
- Adding a delete path to `StatsRepository`. If the residue check finds rows the
  current parser would not produce, that is a finding to report, not a defect to
  fix here.
- The 9 postseason-only seasons.
- Applying `0007_team_bref_id_not_null` to `nba` — named as a preflight in the
  handover procedure, executed on the owner's instruction.
- The migrations F4E-020 and F4E-021 introduce.
- `stats.player_team_season_*`, which the team-season producer owns and which
  already carries the current `team-season-parser-v1`.

# Impact

- **Data (scratch only):** the regular-season aggregate grain grows from 12,042
  to an expected 12,667 distinct player-seasons; postseason and team-stint
  grains change by an amount this card measures rather than predicts.
- **Lineage:** every player-page row moves from `-v1` to `-v4`, which is what
  turns `validate official-stats` from failing to passing for the
  `parser_lineage_violations` counter.
- **Validation:** the first end-to-end exercise of F4E-018's coverage comparison
  against a full rebuild rather than a fixture. A latent defect in the oracle
  surfaces here, and that is a useful outcome, not a blocked card.
- **Reporting:** `backfill player-stats` is expected to go from 577 failed
  entries to 0, which changes what F4E-016's exit-code contract observes on a
  real run for the first time.
- **Schema, API, code:** none.
- **Docs:** two validation documents corrected; one handover procedure added.

# Implementation notes

**Rehearse the whole pipeline, not just the player pages.** The player-page
backfills resolve grains against `core.players`, `core.seasons` and
`core.player_seasons`, so a scratch database seeded with anything less than the
full offline backfill would silently report `unresolved_players_or_seasons`
instead of recovering rows. Run `backfill offline` first and confirm the core
counts before concluding anything about the stats numbers.

**Set `DATABASE_URL` in the child process environment, never in `.env`.**
`get_settings()` is `@lru_cache`d, so an in-process change after the first call
is ignored, and this repository has no `.env` — only `.env.example`. Each
rehearsal command is a fresh `uv run`, which is what makes the env var the
correct mechanism.

**Capture `nba`'s lineage distribution before you start.** It is the only
evidence that will convince a reader six months from now that the rehearsal did
not touch it, and it costs one query.

**The residue check is the point of the coverage artifact, so build it before
the comparison and pass `--coverage-cache-root`.** Without that flag the
comparison runs `unverified` — it trusts the artifact's own claim about the
cache — and an unverified pass is not evidence. The cache does not change during
the rehearsal, so verification is cheap and removes the whole question.

**Expect the coverage build and the backfills to take a long time.** Both parse
all 2,551 cached player pages with BeautifulSoup; a full traversal is on the
order of an hour on this machine. Run them so the result is captured to a file
rather than to a terminal that may be lost, and do not add a progress-polling
loop that inflates the cost.

**Do not "fix" a mismatch by re-running with different flags.** If the recovered
count is not 625, enumerate the difference and name it. Every one of the 634 has
a documented cause; a number that disagrees means either the documentation or
the run is wrong, and both are worth knowing.

**Retitle, do not renumber.** The card keeps id `F4E-024` — F4E-014's review
evidence, the audit disposition, and F4E-022's scope all cite it by id, and the
id is the stable handle. Only the filename and title change.

# Durable knowledge updates

- `docs/validation/OFFLINE_DATABASE_PREPARATION.md` — the corrected Phase 4E
  baseline row counts; deletion of the stale claim that the player-stats
  producer exits nonzero pending F4E-022; the full rebuild-at-`-v4` runbook; and
  the preflighted handover procedure for the persistent `nba` run.
- `docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md` — DB-02 moves from "fixed
  at the parser; persisted rows not yet repaired" to the measured rebuild
  result, and the verified-figures table records the post-rebuild grain counts
  beside the pre-rebuild ones.
- The measured answer to "does an upsert-only rebuild strand rows the current
  parser would not produce?" — recorded wherever the next remediation card will
  look for it, because the question returns on every future parser bump.

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
