---
id: F5-008
title: Decide whether CHH, CHA, and CHO are one franchise or three teams
areas:
  - planning
  - database-read
  - database-schema
  - api
priority: 30
depends_on:
  - F5-006
read:
  - docs/architecture/API_CONTRACT.md
  - docs/domain/BUSINESS_RULES.md
  - src/nba_data/db/models/core.py
validation: []
critical_actions:
  - Applying a migration that adds a franchise entity or lineage edge to a persistent or shared database requires explicit owner approval; authoring a reversible revision does not.
  - Populating core.teams.franchise_id on the existing 37 team rows is a backfill against real data and requires explicit owner approval, even though the column is NULL today.
  - Re-keying or merging existing core.teams rows requires a backfill and explicit owner approval.
---

# Goal

Settle whether the three Charlotte team codes in the archive represent one
franchise or three separate teams, and what — if anything — links them. This is a
narrower question than it was previously filed as, and the narrowing is the
point.

# Evidence and current state

## What the archive actually contains

Measured over all 775 cached team pages, taking the team name from the second
`<h1>` span:

| Code | Name | Seasons | Pages |
|---|---|---|---|
| `CHH` | Charlotte Hornets | 2000–2002 | 3 |
| `CHA` | Charlotte Bobcats | 2005–2014 | 10 |
| `CHO` | Charlotte Hornets | 2015–2025 | 11 |

Related relocations in the same archive, for calibration:

| Code | Name | Seasons |
|---|---|---|
| `NOH` | New Orleans Hornets | 2003–2013 |
| `NOP` | New Orleans Pelicans | 2014–2025 |
| `NJN` | New Jersey Nets | 2000–2012 |
| `BRK` | Brooklyn Nets | 2013–2025 |
| `SEA` | Seattle SuperSonics | 2000–2008 |
| `OKC` | Oklahoma City Thunder | 2009–2025 |

## Effective-dated franchise edges are not needed for this archive

The archive covers **2000–2025** and contains **37 distinct team codes**. Every
one of those 37 codes resolves to **exactly one distinct name across all 775
pages** — no code is ever reused for a different club, and no code changes name
mid-archive. Code ranges are contiguous and non-overlapping.

That removes the strongest argument for effective-dated franchise edges. The
"CHA means the Hornets before 2003 and the Bobcats after 2004" scenario that
would require them describes seasons **outside** this archive: pre-2000 Charlotte
seasons are not in it, and within it `CHA` is only ever *Charlotte Bobcats*.
A simple code → name map is sufficient and correct for every code present.

## What genuinely remains open

A real question survives, and it is a modeling question rather than a data one:
is `CHH` / `CHA` / `CHO` — and by the same logic `SEA` / `OKC`, `NJN` / `BRK`,
`NOH` / `NOP` — **one public entity or several**? `core.teams.franchise_id`
exists in the model and is `NULL` on every row because nothing writes it, so
whichever answer is chosen, nothing currently implements it.

The Charlotte case is the hardest instance because the lineage is contested in a
way the others are not: the Hornets name and history moved to New Orleans in
2003 and were later reassigned back to Charlotte in 2014, while the Bobcats
franchise continued throughout. Any rule that handles Charlotte handles the rest.

## Two lineages both exist, and the NBA does not resolve them with one rule

This is the crux, and it must be understood before question 2 is answerable.
**Organizational continuity and official statistical history point in different
directions for Charlotte, and the NBA has deliberately separated them.**

- **Organizational / legal continuity.** The 1988 Charlotte expansion franchise
  relocated to New Orleans in 2002 and is the same legal entity that is today the
  Pelicans. The 2004 Bobcats were a new expansion franchise.
- **Official statistical history.** On the 2013 renaming, the NBA assigned the
  **1988–2002 Charlotte Hornets records and history to the Charlotte club**,
  joined to the Bobcats' 2004–2014 history. The New Orleans franchise's official
  history correspondingly **begins in 2002-03**.

So the answer is *not* a uniform organizational-lineage rule applied evenly to
`SEA`/`OKC`, `NJN`/`BRK`, and `NOH`/`NOP`. Those three are ordinary relocations
where both lineages agree. Charlotte is the one case where they diverge, because
the league moved the history without moving the entity. A rule that only
implements organizational continuity will contradict the NBA's own published
record for Charlotte; a rule that only implements statistical history will
misstate what the New Orleans entity legally is.

Sources:

- <https://www.nba.com/hornets/charlotte-hornets-name-returns-carolinas>
- <https://www.nba.com/pelicans/news/countdown-pelicans-training-camp-18-days>

Note this affects the *interpretation* only, not the archive's contents: the
archive begins in 2000, so the reassigned pre-2000 seasons are outside it and no
code in it is ambiguous. The decision is about what the API claims a franchise
is, not about repairing data.

# Human decisions or resources

- [ ] **1. Is a franchise a public concept in v1 at all?** If F5-006 settles on
      code-era identities, this may reduce to a documentation note and no schema
      change.
- [ ] **2. Are `CHH`, `CHA`, and `CHO` one franchise or three teams?** State the
      rule, not just the answer. Note that `SEA`/`OKC`, `NJN`/`BRK`, and
      `NOH`/`NOP` are ordinary relocations where organizational continuity and
      official history agree, so a rule that decides them does **not**
      automatically decide Charlotte.
- [ ] **3. Which of the two lineages does the archive model — and does it model
      both?** Organizational continuity gives `CHH` → `NOH` → `NOP`; the NBA's
      official statistical history gives `CHH` + `CHA` → `CHO` with New Orleans
      starting in 2002-03. These are not competing guesses; both are true of
      different things. Decide whether the model carries one, or carries both as
      distinct relations, and say which one the API's `franchise` field means.
- [ ] **4. If franchises are modeled, what populates `franchise_id`?** No source
      page states a franchise, so it would be curated data, not scraped data —
      confirm that is acceptable and decide where the curated list lives and how
      it is validated. Note that writing it to the existing 37 rows is a
      **backfill against real data** and needs approval at the time, not by
      inheritance from this card; the column being NULL today does not make the
      first write a schema change.
- [ ] **5. Is a code → name map sufficient**, given every code maps to exactly
      one name in this archive? Confirm explicitly that **effective-dating is not
      required**, so a future card does not add it on the assumption it is.

# Acceptance criteria

To be finalised once the decisions above are made. At minimum:

- `docs/domain/BUSINESS_RULES.md` states the franchise rule and applies it to
  all four relocation cases in the archive, not only Charlotte.
- It records that no code is reused in this archive and that effective-dated
  franchise edges are therefore not required, with the measurement that supports
  it.
- If franchises are modeled, `franchise_id` has a stated source and a validation
  rule; if not, the column has a stated disposition matching `API_CONTRACT.md`.

# Scope

To be defined. Expected to touch `docs/domain/BUSINESS_RULES.md` and
`docs/architecture/API_CONTRACT.md` always, and `core.teams` plus a curated data
source only if franchises are modeled.

# Out of scope

Extending the archive before 2000, which would change the evidence base and is a
separate acquisition decision. The public team key, which is F5-006. Populating
real team names, which is F4E-015.

# Impact

Low if the answer is "code-era identities, documented". Larger if franchises
become public: a curated franchise source, a populated `franchise_id`, a
migration, and a change to the teams API response.

# Implementation notes

This card is **rewritten, not new**. Its earlier version argued for effective-
dated franchise edges from a "CHA 1988–2002 Hornets vs CHA 2005– Bobcats"
example. That example describes seasons the archive does not contain, and the
measurement above disproves it for every code the archive does contain. Do not
restore it.

Lower priority than the other open team questions precisely because the
measurement shrank it: nothing in the current archive is being read incorrectly
today on account of this being unanswered.

# Durable knowledge updates

- `docs/domain/BUSINESS_RULES.md` — the franchise rule and the code-uniqueness
  measurement.
- `docs/architecture/API_CONTRACT.md` — the `franchise_id` disposition, if it
  changes.

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
