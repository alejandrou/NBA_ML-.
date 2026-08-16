---
id: F4E-025
title: Make parser-version lineage legible
areas:
  - data-quality
  - validation
  - documentation
priority: 45
depends_on: []
read:
  - src/nba_data/scraping/offline_player_stats_backfill.py
  - src/nba_data/scraping/offline_player_postseason_stats_backfill.py
  - src/nba_data/scraping/offline_stats_backfill.py
  - src/nba_data/db/models/stats.py
  - docs/architecture/PLAYER_PAGE_STATS_MAPPING.md
validation: []
critical_actions:
  - A validator that reports stale versions is read-only; anything that rewrites parser_version on existing rows is a write to real data and requires explicit owner approval.
---

# Goal

Give `stats.*.parser_version` a definition. Today it is a free string with three
independent default constants and no registry saying what any value means, which
version is current, or what changed between them. Every bump makes the column
less legible, and there have been two in as many cards.

# Evidence and current state

## Where the versions live

Three constants, in three modules, with no relationship declared between them:

| Constant | Module | Current value |
|---|---|---|
| `DEFAULT_PLAYER_STATS_PARSER_VERSION` | `offline_player_stats_backfill.py:32` | `player-page-parser-v3` |
| `DEFAULT_PLAYER_POSTSEASON_STATS_PARSER_VERSION` | `offline_player_postseason_stats_backfill.py:27` | `player-page-postseason-parser-v3` |
| `DEFAULT_STATS_PARSER_VERSION` | `offline_stats_backfill.py:23` | `team-season-parser-v1` |

Each is a CLI default (`cli/main.py:249`, `:315`, `:383`), so a caller can
override it with any string at all. The column is `String(50)`, `NOT NULL`
(`db/models/stats.py:72`), and nothing validates its contents.

The two player-page constants have moved together so far — F4E-013 took both to
`-v2`, F4E-014 took both to `-v3` — but that is a convention held by whoever
edits them, not a rule anything enforces.

## What a row can no longer tell you

`stats.player_season_*` now holds rows written under `-v1`, `-v2` and, once a
backfill runs, `-v3`. The differences are real and behavioral:

- `-v2` fixed the `YYYY-YY` century rollover (F4E-013), so `-v1` rows carry the
  wrong `season_year` for century-crossing labels.
- `-v3` treats any multi-team marker semantically (F4E-014), so `-v1` and `-v2`
  rows are missing the full-season aggregate for a `5TM` season.

None of that is recoverable from the string itself. It currently lives in source
comments beside the constants, which is better than nothing and is not where a
person querying the table will look.

F4E-022 is already in `tasks/backlog/` and will bump both player-page versions
to `-v4`. That is the third generation in three cards.

## What already consumes it

The stats repositories thread `parser_version` through every write
(`db/repositories/stats.py`), and the validators read stats tables but do not
inspect it. No API endpoint exposes it. So the cost of getting this wrong is
currently borne by whoever queries the database directly — which, for a data
platform, is the primary user.

# Human decisions or resources

- [ ] **1. Is the string the contract, or an index into a registry?** A registry
      — value → what changed, which card, which cards it supersedes — makes the
      column meaningful without a schema change. The alternative is a structured
      value (parser name + integer), which is cleaner but is a data migration.
- [ ] **2. Should the two player-page constants become one?** They have always
      moved together and describe one parser contract over one cached page. If
      that is a rule, it should be enforced by a shared constant rather than by
      remembering to edit both. If it is not a rule, say why they can diverge.
- [ ] **3. What does the validator do when it finds a stale version?** Reporting
      it is clearly in scope and clearly read-only. Whether a stale row is a
      *failure* or an *observation* depends on whether the platform intends the
      table to be homogeneous — which is really a question about whether a
      recovery backfill is expected to run to completion every time.
- [ ] **4. Does anything outside the database need this?** A database view or an
      API field is not obviously warranted: no consumer has asked for one. The
      default should be to add neither until a real query needs it, and to say
      so explicitly rather than leaving it open.

# Acceptance criteria

To be finalised once the decisions above are made. At minimum:

- One place states which parser version is current for each parser, and the
  backfill defaults read from it rather than declaring their own.
- Every version value that exists in the database is described somewhere
  durable, including the ones no longer produced.
- A validator reports rows whose `parser_version` is not current, with counts by
  version and by table, and it writes nothing.
- Adding a version has an obvious single place to record what changed, so the
  next bump does not have to rediscover this.

# Scope

To be finalised.

# Out of scope

- Rewriting `parser_version` on existing rows. Repairing data is F4E-024's
  question; this card makes the state legible, it does not change it.
- Exposing the version through the API. See decision 4.

# Impact

To be finalised.

# Implementation notes

To be finalised.

# Durable knowledge updates

- `docs/architecture/PLAYER_PAGE_STATS_MAPPING.md` — carries the `-v3` lineage
  note today; the registry should supersede it rather than duplicate it.

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
