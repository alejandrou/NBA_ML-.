# NBA Archive Data Audit — Disposition

Maps each defect reported by the *NBA Archive Data Audit* to a status and an
owning task card.

**Status vocabulary.** `confirmed` — reproduced against code, cache, or database,
and a card owns it. `planned` — a card exists and is ready to start; the defect is
not repaired. `deferred` — a real question, but answered by a planning card that
is not ready to start. `accepted` — the reported behavior is a deliberate scope
decision and will not change.

**Nothing here is `fixed`.** No card in this set has been implemented. "Fixed"
becomes available when a card reaches `tasks/done/` and its acceptance criteria
are met.

## Provenance caveat — read before relying on the DB-nn keys

The source audit document is **not in this repository**. Four identifiers are
anchored by surviving references — DB-05 (`player_name_display`), DB-07 (public
`slug`), DB-08 and DB-09 (game logs and boxscores). **The other five (DB-01 …
DB-04, DB-06) are UNRECONCILED.** They were assigned here by defect description,
filling the only free slots, and have never been checked against the original
numbering.

Assigning them by inferred ordering is **not sufficient evidence for a durable
identifier**, so do not treat those five keys as stable. Each row's *description*
is the authoritative identifier, and remains so until someone reconciles the five
against the source audit. The defects themselves are all reproduced and
evidenced; only the labels are in question. Do not cite an unanchored DB-nn key
outside this repository.

## Disposition table

| Key | Defect | Status | Owning card |
|---|---|---|---|
| DB-01 † | `_season_end_year` rolls `1999-00` to **1900**, so season-2000 rows never resolve a grain and are silently dropped | confirmed, planned | [F4E-013](../../tasks/backlog/F4E-013-fix-season-century-rollover-in-player-page-parsing.md) |
| DB-02 † | Multi-team markers hard-coded as `{2TM,3TM,4TM}` in three layers; `5TM` exists in the cache and its season is lost | confirmed, planned | [F4E-014](../../tasks/backlog/F4E-014-treat-any-multi-team-marker-semantically-and-amend-adr-0007.md) |
| DB-03 † | `core.teams.current_name` and `core.team_aliases.name` hold abbreviations; no loader ever supplies a real team name | confirmed, planned | [F4E-015](../../tasks/backlog/F4E-015-populate-real-team-names-from-cached-team-pages.md) |
| DB-04 † | `validate official-stats` reconciles one backfill report against all stats tables; backfill commands exit 0 on partial row failure | confirmed, planned | [F4E-016](../../tasks/backlog/F4E-016-consolidate-backfill-report-validation.md) |
| DB-05 | `player_name_display` is NULL across the player-page-fed stats tables, with nothing documenting why | confirmed as a documentation defect, planned | [F4E-019](../../tasks/backlog/F4E-019-document-player-name-display-source-semantics.md) |
| DB-06 † | Nothing asserts that `core.player_seasons` and `stats.*` agree, so dropped rows are invisible at query time | confirmed, deferred | [F4E-017](../../tasks/planning/F4E-017-classify-expected-stats-coverage-from-cache.md) → [F4E-018](../../tasks/planning/F4E-018-add-a-stats-coverage-invariant-to-the-4e-validator.md) |
| DB-07 | No public `slug`; `core.players.slug` exists and is never written | deferred | [F6-004](../../tasks/planning/F6-004-define-public-player-stats-api-contract.md), with the column's fate in [F4E-021](../../tasks/planning/F4E-021-decide-player-identity-and-alias-model.md) |
| DB-08 | Game logs are absent from the archive | accepted | — |
| DB-09 | Boxscores are absent from the archive | accepted | — |

† DB-nn key provisional; see the provenance caveat.

### Defects found while verifying the audit, which the audit did not report

Two cards in this set own defects that no DB-nn key covers. They were found by
enumerating populations the audit had only counted, and they are listed here so
the table is not mistaken for the complete defect set.

| Defect | Status | Owning card |
|---|---|---|
| A "Did not play" placeholder is counted as a real team row, dropping `milleol01` 2003-04 and producing 577 unloadable rows per backfill run | confirmed, planned | [F4E-022](../../tasks/backlog/F4E-022-stop-treating-did-not-play-placeholders-as-team-rows.md) |
| Three durable documents describe a system the repository is not — 44 stats tables that are 33, a player-page pipeline recorded as not existing, postseason tables recorded as planned | confirmed, planned | [F4E-023](../../tasks/backlog/F4E-023-correct-stale-durable-documentation.md) |

### On DB-08 and DB-09

`docs/architecture/OFFICIAL_STATS_SCHEMA.md` scopes the archive to season-grain
official statistics and excludes game logs and boxscores **by design**. Their
absence is the schema working as specified, not data loss. Reopening either is a
scope decision needing a new acquisition card, not a remediation card.

## Measured evidence

Everything below was measured on **2026-08-15** against the code, the 3,326-file
HTML cache in `data/raw/html/basketball-reference/`, and the `nba` database in
the running `nba_postgres` container.

### Database — the audit's headline figures, verified

| Measure | Value |
|---|---|
| `core.player_seasons` | 12,676 |
| …with regular-season aggregate stats | 12,042 |
| …**without** | **634** |
| Total rows across all 33 `stats` tables | 306,392 |
| `core.seasons` range | 2000–2025, no row below 1999 |

The 12,676 / 12,042 / 634 figures match the audit exactly.

### The 634 decomposed — fully, with no residue

| Bucket | Count | Cause | Owner |
|---|---|---|---|
| Season 2000, no postseason rows | 439 | century rollover | F4E-013 |
| 36 players with 6- or 7-character ids | **184** | player-page discovery pattern | the F4E-012 card |
| Postseason-only seasons | **9** | none — correct as loaded | — |
| `jonesbo02` 2008 | 1 | `5TM` marker | F4E-014 |
| `milleol01` 2004 | **1** | "Did not play" placeholder counted as a team row | F4E-022 |
| **Total** | **634** | | |

**Every one of the 634 has a named cause.** Getting here took two corrections,
and both are recorded because both were the same mistake made at different
scales — reporting a count without enumerating what it contained.

The first revision recorded "185 unclassified" as remaining work. Enumerated in
full, 184 of the 185 belong to exactly 36 players whose Basketball Reference ids
are shorter than nine characters — short surnames such as `foxde01`, `gayru01`,
`linje01`, `lenal01`, `roybr01`, `qizh01` — and the 185th is Bobby Jones, already
owned by F4E-014.

The second revision recorded **10** postseason-only seasons as valid. Nine are.
The tenth, Oliver Miller (`milleol01`) 2003-04, played 48 games for MIN and his
cached page carries the complete row in all eight tables — but the season also
carries a "Did not play" placeholder, and
[`_select_full_season_row`](../../src/nba_data/scraping/normalizers/player_page.py#L373-L385)
counts the placeholder as a second real team row, rejects the season as
`ambiguous_multiple_real_team_rows`, and emits nothing. Scanning all 2,551 cached
pages for that collision finds **exactly one**, so the bucket is now closed
rather than sampled. The nine that remain are `adamsja01` 2020, `hollajo02` 2016,
`jeffrda01` 2023, `jonesdw02` 2013, `lawsoty01` 2018, `mcgratr01` 2013,
`thomptr01` 2023, `vildolu01` 2022, and `wrighdo01` 2016.

### "Did not play" placeholders are not empty, and 1,380 seasons carry one

The placeholder normalizes to exactly one value, not to all-`None`:

```python
{'age': 'Did not play - other pro league'}
```

Measured across the whole cache: **1,380 distinct `(player, season)` pairs**
carry such a row, under **22 distinct reason strings** — `other pro league`
(8,946 cells), `injury` (1,256), `waived` (198), `unsigned` (144), `retired`
(136), and seventeen more down to the bare `Did not play -`.

Because `age` maps to an `Integer` column, every such row raises in
`_stats_values` — `Expected integer-compatible value` — and is recorded as a
failed row. **This is the mechanism behind all 577 `status="failed"` entries in
`reports/player-stats-backfill-2000-2025.json`**, which all carry the single
reason "Player-page stats loader reported failed rows." Sampling 60 failed and 60
loaded entries and re-parsing their pages: 60/60 failed carry a placeholder,
4/60 loaded do. 572 of the 577 loaded rows from their other seasons anyway, for
25,640 rows in total.

No data is lost to this — the rows were never loadable — but every run reports
577 failures that are one normalizer bug, and nothing distinguishes them from a
real failure. F4E-022 owns it; F4E-016 owns the reporting contract that made it
invisible.

### The 184: a discovery-pattern defect, measured end to end

The pattern at `src/nba_data/scraping/offline_player_stats_backfill.py:21`
requires `[a-z0-9]{8,10}`, which cannot match a six- or seven-character id:

| Measure | Value |
|---|---|
| Cached player pages | **2,551** |
| Matching the discovery pattern | 2,515 |
| Excluded | **36** — exactly the 36 players above |

Their pages are cached and parseable, so the data is fully recoverable; their
`core.player_seasons` rows exist because those come from **team** pages, which
discovery handles correctly. This defect is owned by the
[F4E-012 review card](../../tasks/review/F4E-012-fix-player-page-cache-discovery-contract.md).
Its implementation is merged, but the card remains in review pending the user's
testing decision, which is why F4E-017 cannot be started yet.

### Q1 resolved: the repair is in-place, and this is now verified

The prior plan hypothesized that season 1900 never produced persisted rows and
so left **zero stale keys**, making in-place repair provably sufficient rather
than requiring destructive replacement. **Confirmed:** `core.seasons` holds no
row below 1999, so `_resolve_player_season_id` could never resolve a 1900 key and
no write occurred. The failure mode is **omission, not corruption**.

This removes the caveat both prior review rounds carried. A destructive-
replacement card is not required on the evidence available; a rebuild-and-diff
card remains worthwhile as a check, not as a precondition.

### Cache — multi-team marker census

Distinct `(player, season)` pairs whose source team cell matches `^\d+TM$`:

| Marker | Player-seasons | Raw occurrences |
|---|---|---|
| `2TM` | 1,695 | 13,402 |
| `3TM` | 110 | 870 |
| `4TM` | 4 | 30 |
| `5TM` | **1** | 8 |

No `0TM` and no `1TM` anywhere — hence the predicate must mean *count ≥ 2*, not
*any digits*. The single `5TM` is Bobby Jones (`jonesbo02`) 2007-08, whose 2008
season normalizes to **0 rows** and holds **0 stats rows** in the database.

### Cache — team-page `<h1>` contract

All 775 team pages have exactly **three** `<h1>` spans: season label, **team
name**, and the literal `"Roster and Stats"`. **37** distinct team codes span
2000–2025, and every code resolves to exactly **one** distinct name.

### Cache — postseason-only counterexamples

`mcgratr01` 2013 (SAS), `lawsoty01` 2018 (WAS), and `thomptr01` 2023 (LAL) each
yield **16** supported postseason rows — 8 aggregate plus 8 stint — and 8
regular-season rows that are "Did not play" placeholders. All three are correctly
loaded in the database. They are valid coverage, not exceptions to bless.

They also demonstrate why a did-not-play marker must be scoped to one season
type: each has no regular-season stats *and* a full set of postseason stats,
because a player can return for the playoffs. A season-wide "no stats expected"
flag would mark all three as defects.

## Corrections to earlier analysis

Nine claims that earlier rounds carried were re-measured and **do not hold**.
They are recorded here so they are not reintroduced.

1. **The Artest / World Peace example is false for this archive.** Basketball
   Reference renders current names retroactively: `artesro01` is
   "Metta World Peace" on his player page *and* on the 2004 Indiana team page,
   and the set of distinct renderings for him across the entire cache is exactly
   `{"Metta World Peace"}`. There is no "Ron Artest" string in the archive, so it
   contains **no evidence of era-specific naming at all**. Of 2,702 players on
   team pages, 207 render under more than one string, but the variation is
   abbreviation (`"L. James"` / `"LeBron James"`), not history.

2. **Charlotte needs no effective-dated franchise edges.** The archive begins in
   2000, so the "CHA 1988–2002 Hornets vs CHA 2005– Bobcats" case is outside it.
   Measured: `CHH` = Charlotte Hornets 2000–2002, `CHA` = Charlotte Bobcats
   2005–2014, `CHO` = Charlotte Hornets 2015–2025. No code is reused. The
   surviving question — one franchise or three teams — is smaller and is
   [F5-008](../../tasks/planning/F5-008-decide-charlotte-franchise-lineage.md).

3. **`TeamSeasonLoadBatch.team_name` is not un-set — it has no producer.** An
   earlier revision claimed nothing in `src/` ever sets it. It is in fact set at
   `offline_loader.py:109` from a `team_name_by_source` mapping, threaded through
   `offline_backfill.py:70`. The real defect is that the only caller,
   `cli/main.py:205`, never passes the mapping, and the processor never extracts
   a name to put in it. F4E-015's scope was corrected to name
   `offline_processor.py` and `offline_backfill.py`, where the hand-off must
   actually happen.

4. **F4E-013 and F4E-014 cannot merge in either order.** F4E-014 declares
   `depends_on: F4E-013`, so F4E-013 (`-v2`) must land first; the reverse order
   would let `-v2` overwrite `-v3`. Both cards were corrected.

5. **`player_name_display` is on 32 tables, not 24.** 33 tables live in the
   `stats` schema; 32 carry the column and only `player_team_season_roster` does
   not. The **24** figure is the subset that is always NULL — the player-page-fed
   tables. The other 8, the regular-season team-stint tables, are populated from
   the team page's `name_display` cell.

6. **Only 9 of the 634 are validly postseason-only, not 10.** See the
   decomposition above. `milleol01` 2004 is a dropped season, and it was
   miscounted precisely because it *looks* like the valid case from the database
   side — the distinction is only visible in the cached page.

7. **"Did not play" rows do not normalize to all-`None` values.** They carry
   `{'age': '<reason>'}` under 22 distinct reason strings across 1,380 seasons,
   and they fail integer coercion rather than loading as empty rows. Any check
   written against "all values None" would match none of them.

8. **A did-not-play marker does not mean the season has no stats.** It is
   specific to one season type. Five of the nine valid postseason-only seasons
   carry a regular-season placeholder together with real postseason stats.

9. **The multi-team enforcement surface is fourteen code sites and four database
   constraints, not three.** The three sites carrying the `2TM`/`3TM`/`4TM`
   enumeration are where the literal lives, but eleven further sites guard the
   string `TOT` alone — including `get_or_create_team`, `get_or_create_team_alias`,
   `get_or_create_team_season`, and the four `ck_*_not_tot` check constraints — so
   a `5TM` value reaching any of them is treated as a real team. Six durable
   documents also enumerate the closed set. F4E-014's scope was corrected to
   cover all of it.

Additionally, the caveat that `nba_postgres` was unavailable is **stale**: the
container is running and every database figure above was queried directly.

## Not yet filed

Two pieces of work are deliberately **not** in `tasks/` yet. They are downstream
of the discovery repair recorded by the [F4E-012 review
card](../../tasks/review/F4E-012-fix-player-page-cache-discovery-contract.md)
and should be assigned only after that review is accepted:

- **Rebuild and diff** — rebuild the archive into a scratch database and diff it
  against the target, with a re-runnable cache digest over sorted paths and
  content hashes.
- **In-place remediation** — remediate the target archive, gated on that diff.

**These are described, not assigned IDs.** An earlier revision referred to them
as F4E-022 and F4E-023 and other cards cited those IDs in their scope. Minting
identifiers for cards that do not exist creates phantom lifecycle owners — a
reader cannot tell an unfiled card from a lost one, and the ids may not be the
ones eventually issued. The cards that reference this work now name it
descriptively instead.

File both after the F4E-012 review card moves to `tasks/done/`, and assign real
ids then. A destructive replacement card is filed **only if** the rebuild diff
falsifies the Q1 finding above — which the direct database evidence now makes
unlikely.

## Related

- [`tasks/README.md`](../../tasks/README.md) — the card lifecycle.
- [`docs/architecture/OFFICIAL_STATS_SCHEMA.md`](../architecture/OFFICIAL_STATS_SCHEMA.md) — stats scope, and the source of the DB-08/DB-09 acceptance.
- [`docs/decisions/0007-handle-tot-and-trades.md`](../decisions/0007-handle-tot-and-trades.md) — amended by F4E-014.
