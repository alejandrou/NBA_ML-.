---
id: F5-006
title: Define the public team entity and its key for v1
areas:
  - planning
  - api
  - database-read
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

Define **what a public team is** in v1 — a Basketball Reference code-era identity,
a present-day club, or a franchise lineage — and only then settle which column
keys it. Write both into `docs/architecture/API_CONTRACT.md` with the same
permanence the seasons resource already has.

The key question cannot be answered first. `team_id` versus
`basketball_reference_team_id` is a choice between two spellings of the same
entity; it does not decide what that entity is, and picking a spelling now would
freeze an entity definition nobody has made.

# Evidence and current state

## What the loader actually creates

`src/nba_data/scraping/loaders/team_season.py:46` passes the **season's**
abbreviation as `basketball_reference_team_id`, and
`src/nba_data/db/repositories/core.py:58` looks a team up by that exact code. A
row in `core.teams` is therefore one Basketball Reference team code, not a club
and not a franchise. Consequences:

- Relocations and rebrands produce **separate, unlinked rows**: SEA and OKC are
  two teams; NJN and BRK are two teams; CHH, NOH, and NOP are three.
- Nothing joins them. `core.teams.franchise_id` exists in the model
  (`db/models/core.py:45`) and in migration `0001`, but **no code in `src/` ever
  writes it** — the API reads it, the tests fabricate `"bulls"` and `"hawks"`,
  and production data has it `NULL` on every row. Franchise lineage is not
  merely unmodeled; the one column that could carry it is inert.
- `core.team_aliases` carries `from_season_year` / `to_season_year` and is
  populated by the loader, so *some* history exists — but it records
  abbreviation and name per team row, not links between team rows.

## What the domain documentation already says

`docs/domain/BUSINESS_RULES.md:12-16` states that teams change name, city,
abbreviation, and franchise history, and that "future modeling should separate
franchise, team, and aliases." That separation has not happened. This card is
where the API decides what to publish in the meantime.

## What ships today

- `src/nba_data/api/routers/teams.py:28` routes on the surrogate `team_id`;
  `services/teams.py:30` maps `team.id` to it.
- Seasons took the opposite approach and `API_CONTRACT.md` fixes season identity
  permanently. F5-005 documented the team asymmetry under "Team identity" and
  recorded explicitly that it carries **no** permanent v1 guarantee.
- `core.teams` has **no `league` column**, and `queries/teams.py:7` applies no
  filter. Teams are not scoped to NBA and structurally cannot be, while the
  seasons resource permanently promises NBA scope. If a non-NBA team is ever
  loaded, v1 exposes it silently.

# Human decisions or resources

Answer in order. Each later question only makes sense once the earlier one is
settled.

- [ ] **1. What does a public team represent?**
      - a **code-era identity** — what ships today; SEA and OKC are two teams,
        honest to the source, awkward for any client asking "how did this club
        do over time";
      - a **present-day club** — one row per currently-existing club, with
        historical codes folded in as aliases; needs a rule for defunct clubs;
      - a **franchise lineage** — one row per continuous franchise across
        relocations; needs `franchise_id` populated, which no loader does.
- [ ] **2. What happens to historical identities under that answer?** Are SEA
      and OKC one public team or two? If one, which name, abbreviation, and ID
      does the collection show, and how does a client still reach the Seattle
      era? If two, does anything link them?
- [ ] **3. Only then — which column is the public key**, the surrogate `team_id`
      or the natural `basketball_reference_team_id`? If the natural key wins,
      what happens to a row where it is `NULL` — excluded, made `NOT NULL` by a
      migration, or both forms accepted?
- [ ] **4. Does the answer apply retroactively** to the shipped route (a breaking
      change before any client exists), or only to future composite resources
      such as teams-by-season?
- [ ] **5. Does `franchise_id` stay in the response?** It is served and always
      null. Populate it, redefine it, or withdraw it from v1.
- [ ] **6. Should the teams resource be scoped to NBA** to match the season
      guarantee? There is no `league` column on `core.teams`, so this needs a
      join through `team_seasons`, a new column, or an explicit decision that
      teams are deliberately league-agnostic.

# Acceptance criteria

To be finalised once the decisions above are made. At minimum:

- `docs/architecture/API_CONTRACT.md` states, as definitively as it states season
  identity, **what a team is** and **what keys it**, with the "no permanent v1
  guarantee" wording removed.
- `docs/domain/BUSINESS_RULES.md` records the franchise/team/alias decision so
  the loader and the API stop disagreeing about what a team row means.
- Any route, schema, or query change matches those statements, with tests
  covering the chosen entity and key — including at least one relocation case
  (SEA/OKC or NJN/BRK) asserting the agreed behaviour.

# Scope

To be defined. Expected to touch `docs/architecture/API_CONTRACT.md` and
`docs/domain/BUSINESS_RULES.md` always; and, if the entity or key changes,
`src/nba_data/api/routers/teams.py`, `schemas/teams.py`, `services/teams.py`,
`src/nba_data/db/repositories/queries/teams.py`, and the matching tests.

# Out of scope

Players, statistics, write routes, and any resource beyond teams. Changing the
season identity decision, which is settled. Backfilling franchise data — if the
decision needs `franchise_id` populated, that is a separate loader card with its
own acquisition and validation story.

# Impact

Contract-level, and larger than a key rename. If the entity definition changes,
the `api` and `database-read` flows, the OpenAPI surface, and possibly
`core.teams` itself change with it, and `tests/unit/test_team_api.py`,
`test_team_service.py`, and `test_team_query_repository.py` all need updating.
Making `basketball_reference_team_id` non-nullable, adding a `league` column, or
populating `franchise_id` would each additionally require a migration and a data
check against existing rows.

# Implementation notes

Do not promote this card to `tasks/backlog/` until questions 1 and 2 are
answered — the acceptance criteria cannot be made verifiable before then.
Questions 3 through 6 can be answered in the same sitting once 1 and 2 are
settled.

If the decision is "code-era identity, keep `team_id`" — that is, ratify what
ships — this becomes a documentation-only task and should be small. That is a
legitimate outcome, but it should be chosen deliberately rather than reached by
default.

# Durable knowledge updates

- `docs/architecture/API_CONTRACT.md` — replace the provisional "Team identity"
  wording with the settled entity definition and key guarantee.
- `docs/domain/BUSINESS_RULES.md` — record the franchise/team/alias resolution
  under "Teams", replacing "future modeling should separate franchise, team, and
  aliases."

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
