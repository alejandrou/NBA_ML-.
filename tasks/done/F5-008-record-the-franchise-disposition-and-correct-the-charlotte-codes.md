---
id: F5-008
title: Record the franchise disposition and correct the Charlotte codes
areas:
  - documentation
  - api
  - data-quality
priority: 40
depends_on:
  - F5-006
read:
  - docs/architecture/API_CONTRACT.md
  - docs/domain/BUSINESS_RULES.md
  - docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md
  - tasks/done/F5-006-settle-the-public-team-entity-and-key.md
  - src/nba_data/db/models/core.py
  - src/nba_data/scraping/parsers/team_season.py
validation:
  - uv run pytest tests/unit/test_team_api.py
  - uv run ruff check .
  - uv run pytest
  - uv run python scripts/validate_tasks.py
critical_actions: []
---

# Goal

Correct a factual error about Charlotte that both contract documents currently
publish, record the measurement that proves effective-dated franchise edges are
not needed for this archive, and state the standing disposition of
`core.teams.franchise_id` so it reads as a decision rather than an omission.

`F5-006` already answered the modeling question the earlier version of this card
asked. A public team is a code-era identity, franchise lineage is unmodeled, and
`franchise_id` is withdrawn from v1 — decided by the owner on 2026-08-13 and
already written into `API_CONTRACT.md` and `BUSINESS_RULES.md`. What survives is
documentation work: the sentences carrying that decision name the wrong team
codes, the measurement behind it is recorded nowhere durable, and the
Charlotte-specific reason the decision is *structurally* right — not merely
deferred — is unwritten.

No schema change. No migration. No code under `src/` changes.

# Evidence and current state

## Both durable documents name the wrong Charlotte codes

[`API_CONTRACT.md:104`](../../docs/architecture/API_CONTRACT.md#L104) ends:

> The same holds for New Jersey (`NJN`) and Brooklyn (`BRK`), and for Charlotte's
> `CHH`, `NOH`, and `NOP`.

[`BUSINESS_RULES.md:16-18`](../../docs/domain/BUSINESS_RULES.md#L16-L18) repeats
the same triple. **`NOH` and `NOP` are New Orleans, not Charlotte.** Charlotte's
codes in this archive are `CHH`, `CHA`, and `CHO`. The sentence meant to be the
contract's worked example of "a code is an era, not a franchise" instead merges
the two cities whose lineage is hardest to keep apart, and it is the one example
a reader checking Charlotte would land on.

## The measurement, re-run for this card

Every one of the 775 cached team-season pages was parsed with the repository's
own selector — `parse_team_season_page` in
[`parsers/team_season.py:23`](../../src/nba_data/scraping/parsers/team_season.py#L23),
`h1 > span:nth-of-type(2)` — and the name grouped by the code in the cache
filename. Result: **775 pages, 37 distinct codes, zero parse failures, and every
code resolves to exactly one distinct name.** No code is reused for a different
club and no code changes name mid-archive, so a plain code to name map is correct
for every code present and **effective-dating is not required**.

Charlotte and its neighbours, as measured:

| Code | Name | Seasons |
|---|---|---|
| `CHH` | Charlotte Hornets | 2000–2002 |
| `CHA` | Charlotte Bobcats | 2005–2014 |
| `CHO` | Charlotte Hornets | 2015–2025 |
| `NOH` | New Orleans Hornets | 2003–2005, 2008–2013 |
| `NOK` | New Orleans/Oklahoma City Hornets | 2006–2007 |
| `NOP` | New Orleans Pelicans | 2014–2025 |

## Three corrections to this card's own earlier evidence

The re-run disproves three claims the earlier revision carried. They must not be
restored.

1. **"Code ranges are contiguous and non-overlapping" is false.** `NOH` covers
   2003–2005 and 2008–2013, interrupted by `NOK` for 2006–2007. A code's season
   set is not always an interval. `NOH` is the only such code, and it still
   resolves to exactly one name across both runs — so this weakens nothing about
   the code-to-name conclusion, but the contiguity claim itself is wrong and
   would be a trap for anyone reasoning about season ranges from it.
2. **The relocation list was incomplete.** It omitted `NOK` entirely and omitted
   `VAN` (Vancouver Grizzlies, 2000–2001) to `MEM` (Memphis Grizzlies,
   2002–2025). The archive holds **five** code transitions, not four:
   `VAN`/`MEM`, `SEA`/`OKC`, `NJN`/`BRK`, `CHA`/`CHO` (a rename in place), and
   the `CHH`/`NOH`/`NOK`/`NOP` chain.
3. **The code-to-name map is not invertible.** `CHH` and `CHO` both render
   *Charlotte Hornets* — the only name in the archive carried by two codes. The
   map is a function from code to name and never the reverse; a name lookup would
   be ambiguous for exactly this pair.

## Why one `franchise_id` column could not have carried the answer anyway

Two lineages both exist for Charlotte, and the NBA deliberately separated them:

- **Organizational continuity.** The 1988 Charlotte expansion franchise relocated
  to New Orleans in 2002 and is the same legal entity that is today the Pelicans.
  The 2004 Bobcats were a new expansion franchise.
- **Official statistical history.** On the 2013 renaming the NBA assigned the
  1988–2002 Charlotte Hornets records to the Charlotte club, joined to the
  Bobcats' 2004–2014 history. The New Orleans franchise's official history
  correspondingly begins in 2002-03.

Sources:

- <https://www.nba.com/hornets/charlotte-hornets-name-returns-carolinas>
- <https://www.nba.com/pelicans/news/countdown-pelicans-training-camp-18-days>

Organizational continuity gives `CHH` to `NOH` to `NOK` to `NOP`. Official
history gives `CHH` plus `CHA` to `CHO`, with New Orleans starting in 2002-03.
`SEA`/`OKC`, `NJN`/`BRK`, and `VAN`/`MEM` are ordinary relocations where the two
agree; Charlotte is the one case where they diverge, because the league moved the
history without moving the entity.

A single scalar `core.teams.franchise_id`
([`core.py:46`](../../src/nba_data/db/models/core.py#L46)) can express one
lineage, not two. So `F5-006`'s decision is not a deferral Charlotte is still
waiting on — Charlotte is the case that shows a lineage column would have had to
pick a side, silently, in the one place it matters. That reasoning is what this
card records.

## The disposition is already consistent, just unstated

`franchise_id` is nullable in the model, created by migration `0001`, and written
by nothing in `src/`. It is withdrawn from the API response
([`API_CONTRACT.md:115`](../../docs/architecture/API_CONTRACT.md#L115)), pinned by
`tests/unit/test_team_api.py:275-288`, and left in the schema on purpose —
`F4E-021` states that difference explicitly when it drops `core.players.slug` and
defers `franchise_id` to this card. Nothing needs to change; it needs to be
written down as the standing answer.

## A link this card breaks

[`ARCHIVE_DATA_AUDIT_DISPOSITION.md:231`](../../docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md#L231)
links `F5-008` at `tasks/planning/`. Moving this card breaks that link, so it is
in scope.

# Human decisions or resources

- [x] **1. Is a franchise a public concept in v1 at all?** No. `F5-006` decisions
      2 and 5 (owner, 2026-08-13) settled that franchise lineage is unmodeled and
      unpromised and that `franchise_id` is withdrawn from the response. This
      card is therefore documentation, not schema work.
- [x] **2. Are `CHH`, `CHA`, and `CHO` one franchise or three teams?** **Three
      teams.** The rule is `F5-006`'s and applies uniformly: a public team is one
      Basketball Reference team code, and no code is linked to any other. It
      decides Charlotte the same way it decides `SEA`/`OKC` — not because the
      cases are alike, but because the rule refuses to assert lineage in either.
- [x] **3. Which lineage does the archive model — and does it model both?**
      **Neither, and that is the answer, not a gap.** The two lineages disagree
      for Charlotte, so a single `franchise_id` would have to pick one and would
      then contradict either the NBA's published record or the legal entity. The
      teams resource makes no lineage claim, so it has no `franchise` field to
      define. Both lineages are recorded in prose so a future card starts from the
      distinction rather than rediscovering it.
- [x] **4. What populates `franchise_id`?** Nothing, now or in v1. Standing
      disposition: the column stays in `core.teams`, unwritten and unserved. It is
      not dropped — unlike `core.players.slug`, a real generator exists (curated
      lineage data), so the column has a plausible future. Reinstating it requires
      a card that names **which** lineage it means, states where the curated list
      lives, and carries its own backfill approval. No such card is opened here.
- [x] **5. Is a code-to-name map sufficient?** Yes, and **effective-dating is not
      required** — proven by the 775-page measurement above. Recorded durably so a
      later card does not add it on the assumption that it is needed. The one
      qualification is that the map is not invertible: `CHH` and `CHO` share the
      name *Charlotte Hornets*.

# Acceptance criteria

## The Charlotte error is corrected

- `API_CONTRACT.md:104` no longer attributes `NOH` or `NOP` to Charlotte. Its
  worked examples use correct code sets: Charlotte is `CHH`, `CHA`, `CHO`; New
  Orleans is `NOH`, `NOK`, `NOP`.
- `BUSINESS_RULES.md:16-18` carries the same correction, and the two documents
  state the same code sets as each other.
- `grep -n "CHH" docs/architecture/API_CONTRACT.md docs/domain/BUSINESS_RULES.md`
  shows no line listing `CHH` alongside `NOH` or `NOP` as one city's codes.

## The measurement is recorded

- `BUSINESS_RULES.md`'s Teams section states that across the 775 cached
  team-season pages every one of the 37 distinct team codes resolves to exactly
  one team name, that no code is reused, and that **effective-dated franchise
  edges are therefore not required for this archive**.
- It names how the measurement was taken — the `h1 > span:nth-of-type(2)`
  selector in `parsers/team_season.py` — so the claim is reproducible rather than
  asserted.
- It records the two qualifications that make the claim safe to rely on: `NOH`'s
  season range is interrupted by `NOK` and is therefore not an interval, and
  `CHH` and `CHO` share a name so the map is code-to-name only.
- It states the scope bound: the claim holds for the 2000–2025 archive, and
  extending the archive earlier would reopen it.

## The franchise rule covers every case in the archive

- `BUSINESS_RULES.md` applies the code-era rule to all five transitions present —
  `VAN`/`MEM`, `SEA`/`OKC`, `NJN`/`BRK`, `CHA`/`CHO`, and the
  `CHH`/`NOH`/`NOK`/`NOP` chain — rather than to Charlotte alone.
- It records that Charlotte's two lineages diverge, that the divergence is why a
  single lineage column is not the right shape, and that `SEA`/`OKC`, `NJN`/`BRK`,
  and `VAN`/`MEM` are cases where the two lineages agree. Both nba.com sources are
  cited.

## `franchise_id` has a stated disposition

- `BUSINESS_RULES.md` states that `core.teams.franchise_id` remains in the schema
  and is written by nothing, and that this is the standing disposition rather than
  pending work.
- `API_CONTRACT.md`'s "Fields withdrawn from v1" entry for `franchise_id` is
  consistent with it and says that reinstating the field requires naming which
  lineage it carries.
- No file under `src/`, `alembic/`, or `tests/` changes. `git diff --stat` after
  the change lists only files named in `# Scope`.

## Links and cross-references

- `ARCHIVE_DATA_AUDIT_DISPOSITION.md:226-231` points at this card's new path under
  `tasks/backlog/`, and its "Measured:" list is consistent with the numbers
  recorded in `BUSINESS_RULES.md`.
- `uv run python scripts/validate_tasks.py` passes.
- `uv run pytest tests/unit/test_team_api.py` passes unchanged — the response
  shape is untouched and this card must not alter it.

# Scope

`docs/architecture/API_CONTRACT.md`, `docs/domain/BUSINESS_RULES.md`, and
`docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md`.

# Out of scope

All code, schema, and migrations. `core.teams.franchise_id` is documented, never
altered or dropped — a drop would need its own card and its own reasoning, and the
"plausible future generator" argument in `F4E-021` is the reason it survives.
Populating any lineage data. Any curated franchise source. Serving alias history
from the API, which `F6-004` owns. Extending the archive before 2000, which would
change the evidence base and is an acquisition decision. Real team names, which is
`F4E-015`.

`ARCHIVE_DATA_AUDIT_DISPOSITION.md` carries other stale `tasks/planning/` links in
rows DB-06 and DB-07 for cards that have since moved. They are pre-existing and
unrelated; leave them so they stay findable for whoever repairs that table.

# Impact

- **Contract:** the Charlotte example in `API_CONTRACT.md` becomes correct. No
  field, route, status code, or response shape changes, so no client-visible
  behaviour changes.
- **Domain rules:** `BUSINESS_RULES.md` gains the code-uniqueness measurement and
  the franchise disposition, and its Charlotte example stops naming New Orleans.
- **Schema:** unchanged. `franchise_id` keeps its column, its nullability, and its
  emptiness.
- **Future cards:** a lineage card, if one is ever opened, starts from a written
  distinction between the two lineages instead of rediscovering it, and knows it
  must choose one explicitly.

# Implementation notes

Read `tasks/done/F5-006-settle-the-public-team-entity-and-key.md` first. This card
adds nothing to its decisions and must not reopen them — every rule stated here is
`F5-006`'s rule applied to cases it did not enumerate.

Match the register of the existing "Team identity" section. It states identity as
a permanent guarantee, and the franchise disposition is part of that guarantee,
not a caveat appended to it. Do not introduce deferral wording — `F5-006`
deliberately removed all of it, and its sad path greps for `deferred`,
`open decision`, and `no permanent` to prove it stays removed.

When correcting line 104, keep the sentence's job intact: it is the contract's
worked example of "a code is an era, not a franchise". Charlotte is a *better*
example than Seattle once the codes are right, because `CHH` and `CHO` share a
name — two separate public teams that a client matching on name alone would merge.
That is worth one clause rather than losing.

The measurement is reproducible offline against the existing cache; nothing needs
re-fetching. Group by the code in the `teams-<code>-<season>.html-<hash>.html.gz`
filename and take `ParsedTeamSeasonPage.team_name` from `parse_team_season_page`.
Expect 775 pages, 37 codes, one name each, no issues.

# Durable knowledge updates

- `docs/domain/BUSINESS_RULES.md` — the franchise rule across all five archive
  transitions, the 775-page / 37-code measurement with its two qualifications, and
  the standing `franchise_id` disposition.
- `docs/architecture/API_CONTRACT.md` — the corrected Charlotte codes and the
  condition under which `franchise_id` could return.
- `docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md` — the repaired card link and
  consistent measurement numbers.

# Review evidence

## Automated validation

- Command: `uv run pytest tests/unit/test_team_api.py`
- Result: **12 passed** in 0.77s. The teams response shape is untouched, and the
  `franchise_id` withdrawal assertions at `tests/unit/test_team_api.py:275-288`
  still hold.
- Command: `uv run ruff check .`
- Result: **All checks passed!**
- Command: `uv run pytest`
- Result: **949 passed, 27 skipped** in 17.33s. No test changed in this card.
- Command: `uv run python scripts/validate_tasks.py`
- Result: recorded below, run after this card moved to `tasks/review/`.
- Command: `git diff --stat`
- Result: three files, all named in `# Scope` —
  `docs/architecture/API_CONTRACT.md`, `docs/domain/BUSINESS_RULES.md`, and
  `docs/validation/ARCHIVE_DATA_AUDIT_DISPOSITION.md`. Nothing under `src/`,
  `alembic/`, or `tests/`. `git diff --check` is clean.

### Review pass

A review of the diff against the acceptance criteria found two defects, both
fixed in place before closing:

1. `API_CONTRACT.md` — the new Charlotte paragraph ended on "the code is what v1
   promises", which collided with the following paragraph's "That is what v1
   promises, not a gap awaiting repair" and left that "That" with two possible
   antecedents. The clause now reads "Only the code tells them apart, and only
   the code is keyed."
2. `ARCHIVE_DATA_AUDIT_DISPOSITION.md` — the repaired reference named the card by
   ID without linking it. With the card in `tasks/done/` the link target is
   permanent, so the hyperlink is restored.

The review also confirmed no other document in `docs/`, `README.md`, or
`.agents/` repeats the wrong Charlotte triple, and that `franchise` appears only
in the three files this card touches.

### The measurement was re-run, not copied

The card's numbers were reproduced offline against the existing cache before any
document was edited — 775 files matching
`data/raw/html/basketball-reference/teams-<code>-<season>.html-<hash>.html.gz`,
each parsed with `parse_team_season_page`, grouped by the code in the filename:

- **775 pages, 37 distinct codes, 0 parse failures or team-name issues.**
- Every code resolves to exactly one name; no code carries two.
- One name is carried by two codes: *Charlotte Hornets* by `CHH` and `CHO`.
- Exactly one code has a non-interval season set: `NOH` (2003–2005, 2008–2013).
- Charlotte and New Orleans measured: `CHH` 2000–2002, `CHA` 2005–2014,
  `CHO` 2015–2025, `NOH` 2003–2005 + 2008–2013, `NOK` 2006–2007, `NOP`
  2014–2025 — matching the card's table exactly.

No network access was involved. The script was disposable and lives outside the
repository.

## Manual happy path

1. Run
   `grep -n "CHH" docs/architecture/API_CONTRACT.md docs/domain/BUSINESS_RULES.md`.
   Expected: no line presents `CHH` as one city's codes together with `NOH` or
   `NOP`. Two `BUSINESS_RULES.md` lines do name them on one line — the
   `CHH` to `NOH` to `NOK` to `NOP` transition chain and the organizational
   lineage — and both say explicitly that these are different cities.
2. Read `docs/architecture/API_CONTRACT.md:104-106` ("Team identity"). Expected:
   the worked example still makes the "a code is an era, not a franchise" point,
   New Orleans now owns `NOH`/`NOK`/`NOP`, and Charlotte is `CHH`/`CHA`/`CHO`
   with the shared-name warning that makes it the better example.
3. Read the three new `###` subsections at the end of the "Teams" section of
   `docs/domain/BUSINESS_RULES.md`. Expected: the 775-page / 37-code measurement
   with the `h1 > span:nth-of-type(2)` selector named, the statement that
   effective-dated franchise edges are **not required**, the two qualifications
   (`NOH` non-interval, `CHH`/`CHO` share a name), the 2000–2025 scope bound, both
   Charlotte lineages with the two nba.com sources, and the standing
   `franchise_id` disposition.
4. Read the `franchise_id` bullet under "Fields withdrawn from v1" in
   `API_CONTRACT.md`. Expected: it agrees with `BUSINESS_RULES.md` and states
   that reinstating the field requires naming which lineage it carries.
5. Start the API and request a team: the response still carries only
   `basketball_reference_team_id`, `current_abbreviation`, and `current_name`.

Expected result: both documents state the same Charlotte and New Orleans code
sets, the measurement is reproducible from what is written, and no served
behaviour changed.

## Manual sad path

1. Run `grep -rni "deferred\|open decision\|no permanent"` over
   `docs/architecture/API_CONTRACT.md` and `docs/domain/BUSINESS_RULES.md`.
   Expected: **no matches** — `F5-006` removed that register and this card does
   not reintroduce it.
2. Run `git diff --stat` and look for any path under `src/`, `alembic/`, or
   `tests/`. Expected: none.
3. Search either document for a claim that code season ranges are contiguous, or
   that a name can be mapped back to a code. Expected: neither claim appears;
   `BUSINESS_RULES.md` states the opposite of both.
4. Search `docs/` for `tasks/planning/F5-008`. Expected: no match — the stale
   link in `ARCHIVE_DATA_AUDIT_DISPOSITION.md` is gone.

Expected result: nothing reopens `F5-006`'s decisions, no code or schema moved,
and no superseded claim survives.

## Known limitations

- **The card link points at `tasks/done/`, not `tasks/backlog/`.** The criterion
  asked for this card's path under `tasks/backlog/`, which was already stale when
  implementation began — the card moves on to `active/`, `review/`, and `done/`,
  so a `backlog/` link would break on the next move exactly as the original one
  did. With the card closed, `tasks/done/` is its permanent path, so the link
  resolves and matches the `F4E-012` link convention already used in that file.
  The reference also points at `docs/domain/BUSINESS_RULES.md`, which is where
  the answer itself lives.
- `ARCHIVE_DATA_AUDIT_DISPOSITION.md` rows DB-06 and DB-07 still carry stale
  `tasks/planning/` links. Left untouched per `# Out of scope`.
- The measurement is bounded by the cache as it stands: 2000–2025, 775 pages.
  Acquiring earlier seasons would reopen the code-uniqueness claim, and both the
  card and `BUSINESS_RULES.md` say so.
- `core.teams.franchise_id` is documented, not dropped. Nothing about the column,
  its nullability, or its emptiness changed.
