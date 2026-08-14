---
id: F5-006
title: Settle the public team entity and key in the contract documents
areas:
  - documentation
  - api
priority: 60
depends_on:
  - F5-005
read:
  - docs/architecture/API_CONTRACT.md
  - docs/domain/BUSINESS_RULES.md
validation:
  - uv run ruff check .
  - uv run pytest
critical_actions: []
---

# Goal

Record the settled definition of a public team and its key in
`docs/architecture/API_CONTRACT.md` and `docs/domain/BUSINESS_RULES.md`, with the
same permanence the seasons resource already has, and remove the "no permanent v1
guarantee" wording.

This card writes the decision down. `F5-007` implements it. They are split
because the documents must state the target before the route, schema, and
migration are changed to match, and because a reviewer should be able to check
the wording independently of the code change.

# Evidence and current state

The four open decisions were resolved by the user on 2026-08-13:

- **A public team is a code-era identity.** One row per Basketball Reference team
  code — which is what the loader already produces:
  `src/nba_data/scraping/loaders/team_season.py:46` passes the season's
  abbreviation as `basketball_reference_team_id`, and
  `src/nba_data/db/repositories/core.py:58` looks a team up by that exact code.
  SEA and OKC are two public teams; NJN and BRK are two; CHH, NOH, and NOP are
  three. Nothing links them, and v1 does not promise that anything will.
- **The public key is `basketball_reference_team_id`**, the natural key, chosen
  over the surrogate `team_id` because it is reproducible across database
  rebuilds — the exact property `API_CONTRACT.md:98` currently warns clients that
  `team_id` lacks.
- **`franchise_id` is withdrawn from v1.** It is served on every team response
  (`src/nba_data/api/schemas/teams.py:9`) and is always `null`: it exists in the
  model (`db/models/core.py:45`) and in migration `0001`, but no code in `src/`
  ever writes it. It promises lineage the data cannot back.
- **Teams are explicitly league-agnostic.** `core.teams` has no `league` column
  and `db/repositories/queries/teams.py:7` applies no filter. Unlike seasons,
  which v1 fixes to NBA permanently (`API_CONTRACT.md:120`), the teams resource
  is deliberately not league-scoped, and that is documented behaviour rather than
  an oversight.

Two facts constrain how the key decision gets written up, both verified against
the migrations:

- Uniqueness **is** already enforced. Migration `0002_core_team_player_season.py:20-25`
  creates `uq_core_teams_bref_id` on `basketball_reference_team_id`. The natural
  key is therefore safe to publish as a key.
- The column is still **nullable** (`0001_initial_raw_core.py:80`,
  `db/models/core.py:43`). What v1 promises about a row with a null natural key
  is a contract statement this card must make; `F5-007` enforces it.
- `TOT` is already excluded at the database level by
  `ck_core_teams_bref_id_not_tot` (`0002:26-31`), consistent with the existing
  rule that `TOT` is never a real team.

# Human decisions or resources

- [x] **1. What does a public team represent?** A **code-era identity** — one row
      per Basketball Reference team code. Ratifies what ships.
- [x] **2. What happens to historical identities?** SEA and OKC are **two**
      public teams, and nothing links them in v1. Per-row name and abbreviation
      history remains available through `core.team_aliases`, which the loader
      already populates with `from_season_year` / `to_season_year`. Franchise
      lineage is explicitly not a v1 concept.
- [x] **3. Which column is the public key?** `basketball_reference_team_id`.
- [x] **4. Does it apply retroactively?** Yes — to the shipped route, now, before
      any client exists. Deferring would mean shipping v1 with a key the contract
      already says is provisional.
- [x] **5. Does `franchise_id` stay in the response?** No. Withdrawn from v1, to
      be reintroduced only with the loader card that actually populates it.
- [x] **6. Is the teams resource NBA-scoped?** No. Deliberately league-agnostic,
      stated as such so the asymmetry with seasons is intentional and visible.

# Acceptance criteria

- `API_CONTRACT.md`'s "Team identity" section states that a public team is one
  Basketball Reference team code, and that `basketball_reference_team_id` is the
  public key, as definitively as the "Season identity" section states season
  identity.
- The "no permanent v1 guarantee" sentence and the "open decision, deliberately
  deferred" wording are gone, along with the paragraph deferring to F5-006.
- The document states, for a relocation, that SEA and OKC are two separate public
  teams and that v1 offers no link between them — using a named example.
- The document states that the teams collection is **not** league-scoped, and
  explicitly contrasts that with the permanent NBA scope of seasons.
- The document states what happens to a row whose `basketball_reference_team_id`
  is null, matching what `F5-007` will enforce.
- `franchise_id` is documented as withdrawn from v1 rather than silently dropped,
  so a reader of the contract history can tell it was a decision.
- `BUSINESS_RULES.md`'s "Teams" section replaces "future modeling should separate
  franchise, team, and aliases" with the settled franchise/team/alias resolution:
  a team row is a code-era identity, aliases carry per-row history, franchise
  lineage is unmodeled and not promised.
- The documents no longer contradict each other or the loader about what a team
  row means.
- No source file under `src/` changes in this card.

# Scope

`docs/architecture/API_CONTRACT.md` and `docs/domain/BUSINESS_RULES.md` only.

# Out of scope

All code. The route, schemas, services, queries, migrations, and tests are
`F5-007`. Players, statistics, and write routes. Season identity, which is
settled. Backfilling or populating franchise data.

# Impact

Contract-level. `API_CONTRACT.md` becomes the specification `F5-007` implements
against, so a wording error here propagates into the route change. No runtime
behaviour changes in this card; `validation:` runs only to prove that.

`F6-004` is blocked on this decision and can be prepared once these documents
land.

# Implementation notes

Match the register of the existing "Season identity" section — it is the model
for how permanently this repository states an identity guarantee.

Write the null-key rule and the F5-007 enforcement together so they cannot
disagree: if the contract says null-key rows are excluded, F5-007 excludes them;
if it says the column becomes `NOT NULL`, F5-007 writes that migration.

Do not describe the route as already using the natural key — at the end of this
card it does not. Write the contract in the present tense as a specification, and
let `F5-007` make the code true.

# Durable knowledge updates

This card *is* the durable knowledge update. Both documents above are its
deliverable.

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
