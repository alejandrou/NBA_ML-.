---
id: F4E-021
title: Decide the player identity and alias model
areas:
  - planning
  - data-quality
  - database-schema
  - api
priority: 35
depends_on: []
read:
  - src/nba_data/db/repositories/core.py
  - src/nba_data/db/models/core.py
  - docs/domain/BUSINESS_RULES.md
  - docs/architecture/OFFICIAL_STATS_SCHEMA.md
validation: []
critical_actions:
  - Adding an alias table or a name-source column requires a new Alembic revision and explicit owner approval.
  - Writing core.players.slug for the first time requires a backfill and explicit owner approval.
---

# Goal

Decide what `core.players.full_name` is supposed to mean, and whether the
player-page `<h1>` name earns a distinct field, an alias table, or nothing at
all. Today the value is defined only by load order, which is true but
undocumented.

# Evidence and current state

## What `full_name` actually holds

[`get_or_create_player`](../../src/nba_data/db/repositories/core.py#L147-L175):

```python
creation_name = name or player_id
...
if player is not None:
    if name and _is_fallback_or_empty(player.full_name, fallback=player_id):
        player.full_name = name
```

On creation the name is stored, falling back to the Basketball Reference id. On
every later encounter the stored name is **only** replaced if the existing value
is still the fallback. So `full_name` is *the first non-fallback name any loader
supplied* — effectively the debut-era name, and dependent on the order seasons
were loaded. Reload the archive in a different order and the value can change.

## The naming evidence, measured

This is the part that most changes the shape of the decision. Over all 775
cached team pages and the corresponding player pages:

- Basketball Reference renders the player's **current** name retroactively.
  `artesro01` is rendered **"Metta World Peace"** on his player page `<h1>` *and*
  on the 2004 Indiana team page. The set of distinct renderings for him across
  the entire cache is exactly `{"Metta World Peace"}`. There is no "Ron Artest"
  string in the archive.
- Of the 2,702 players appearing on team pages, **207** render under more than
  one string. None of the variation is historical, but it is not all one kind:
  - **abbreviation** — `{"LeBron James", "L. James"}`,
    `{"Victor Wembanyama", "V. Wembanyama"}`;
  - **spelling / transliteration** — `{"Efthimios Rentzias",
    "Efthimi Rentzias"}`, where neither form abbreviates the other.

So "the debut-era name" is a description of the *load mechanism*, not of the
data: every source in this archive prints the same current name for a given
player. An alias model built on this archive would be modeling rendering
variants, not historical identities.

The two kinds pull differently on question 2 below, which is why the distinction
is worth keeping. Abbreviations are derivable — a consumer wanting `"L. James"`
can produce it from `"LeBron James"` — so storing them buys nothing. A
transliteration variant is **not** derivable, so if anything in this archive
justifies an alias row, it is that second category, and it is small. Count it
before deciding: "207 players vary" and "how many vary in a way we could not
reconstruct" are very different numbers, and only the second is an argument for
a table.

## The inert column

`core.players.slug` is declared at
[core.py:85](../../src/nba_data/db/models/core.py#L85) and **no code in `src/` ever
writes it** — the same shape of defect as `core.teams.franchise_id`. Whether a
public player slug exists is F6-004's contract decision; whether this column is
its home is this card's.

# Human decisions or resources

- [ ] **1. What is `core.players.full_name` defined to be?** The candidates are
      "the first non-fallback name observed" (what the code does), "the current
      name as the source renders it" (what the data actually is), or "the name
      as of the player's most recent season". Note the first two are almost
      always the same value in this archive; the difference is whether the
      definition is load-order dependent.
- [ ] **2. Does anything need an alias model at all?** Given that the archive
      contains no era-specific names, a `player_aliases` table would today hold
      only rendering variants. Measure the non-derivable subset first — the
      spelling and transliteration cases, not the abbreviations — then decide
      whether that is worth modeling, worth deferring until a source with
      historical names exists, or worth rejecting.
- [ ] **3. Should the fallback-to-id behavior stay?** `full_name` is `NOT NULL`,
      so a player with no observed name gets its id as a name. Is that
      acceptable, or should the column become nullable so "unknown" is
      representable as NULL rather than as a fake name?
- [ ] **4. Does `core.players.slug` get populated, dropped, or reserved, and if
      populated, what generates it?** **This card owns the whole slug decision**,
      including the generation rule — not only the column's fate. An earlier
      revision split it with F6-004 such that each card deferred "what generates
      it" to the other, and the question was owned by neither.

      The constraint that decides it: a slug must be stable across a database
      rebuild, so it cannot derive from the surrogate `players.id`. That leaves
      the Basketball Reference player id and a normalized name. The naming
      evidence above rules out the normalized name — Basketball Reference
      re-renders names retroactively, so a name-derived slug would change under
      the archive on a re-scrape — which makes the Basketball Reference id the
      only stable candidate in this archive. Confirm or refute that, and if it is
      confirmed, note that the slug is then a copy of an identifier the API
      already has and the honest question becomes whether it earns a column at
      all.

      F6-004 decides only whether the API **exposes** a slug, and consumes
      whatever this card decides exists.
- [ ] **5. If the definition changes, is a migration or backfill needed,** and
      does it belong to this card or to the remediation cards?

# Acceptance criteria

To be finalised once the decisions above are made. At minimum:

- `docs/domain/BUSINESS_RULES.md` states what `full_name` means and whether it
  is load-order dependent, with the same permanence as the player-identity rule
  it already carries.
- The alias question is answered explicitly — including "no alias model in v1",
  which is a legitimate answer given the measured evidence.
- `core.players.slug` has a stated disposition **and**, if it is populated, a
  stated generation rule with the stability property it guarantees across a
  rebuild.
- Any code change matches the stated definition, with a test asserting the
  documented behavior including the reload-order case.

# Scope

To be defined. Expected to touch `docs/domain/BUSINESS_RULES.md` always, and —
only if the definition changes — `src/nba_data/db/repositories/core.py`, the
`core.players` model, a migration, and tests.

# Out of scope

`player_name_display` on the stats tables, which F4E-019 settles as *the name as
printed in this source row*. The public API's player key, and whether the API
exposes a slug at all, which are F6-004 — but **not** the slug's existence or
generation rule, which are question 4 above. Team identity and franchise lineage,
which are F5-006 and F5-008.

# Impact

`core.players.full_name` is served by any future player API resource, so a
definition change is a contract change. Making the column nullable or populating
`slug` would each need a migration.

# Implementation notes

Do not promote to `tasks/backlog/` until questions 1 and 2 are answered — the
rest depend on them.

The most likely honest outcome is: keep the current behavior, document it as
"the first non-fallback name observed, which in this archive is the source's
current name", and decline the alias model until a source with historical names
exists. That is a real decision and should be chosen deliberately, not reached
by leaving the card open.

Note for whoever answers this: the older framing of this question rested on the
Artest / World Peace example, which was measured and **does not hold** — see the
evidence above. Do not restore it.

# Durable knowledge updates

- `docs/domain/BUSINESS_RULES.md` — the `full_name` definition, the alias
  decision, and the finding that Basketball Reference renders current names
  retroactively.

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
