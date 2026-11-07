---
id: F8-015
title: Add play-by-play to the predictor
track: data
areas:
  - planning
  - ml
  - scraping
  - database-schema
priority: 78
depends_on:
  - F8-009
read:
  - docs/ml/PREDICTOR_PLAN.md
  - docs/ml/TEAM_PREDICTOR_EVALUATION.md
  - docs/validation/PER_GAME_ACQUISITION_PILOT.md
  - docs/validation/GAME_DATASET_ACQUISITION.md
  - docs/decisions/0020-take-per-game-data-from-basketball-reference.md
  - src/nba_data/scraping/parsers/play_by_play.py
  - src/nba_data/scraping/parsers/box_score.py
  - src/nba_data/ml/splits.py
validation: []
critical_actions:
  - Live acquisition of about 8,300 play-by-play pages (about 14.5 hours), if the selected window is last_5, through a gated command copied from F8-004's — the owner's direct instruction per batch.
  - Only if the evaluation keeps play-by-play features, applying their schema to the persistent nba database.
---

# Goal

Stage 4, step two: possessions, team profiles, and regularized impact from
play-by-play, kept only if they beat the best model that needs no new
acquisition, on the same games.

# Evidence and current state

- The parser exists (`parsers/play_by_play.py`); 29 of 30 pilot games
  reconcile. Lineups between periods are not logged (pilot finding 12), and
  `pbpstats` does not read these pages (ADR 0020).
- Period-start lineups are recoverable offline. A probe on 2026-11-06 took the
  players with seconds in a period's box, less those whose first substitution
  there brings them in. On the 20 in-scope pilot games, 178 of 178 period
  starts resolve to five, no substitution or event contradicts the lineup, and
  walking the game reproduces 392 of 394 published plus-minus lines, 17 of 18
  games exactly. On all 30 games, 269 of 270 period starts resolve. Record:
  `docs/validation/PER_GAME_ACQUISITION_PILOT.md`.
- Same-clock order decides that result: scoring must apply before
  substitutions. In feed order only 153 of 394 lines are exact.
- All 14,452 cached box scores have the four quarter boxes, so reconstruction
  needs no acquisition beyond the play-by-play pages. `parsers/box_score.py:225`
  still reads only each period's points.
- All 4,670 field-goal attempts in the pilot's games from 2014-15 on state a
  distance or "at rim".
- Cost at F8-006's pace (6.29 s per page): about 8,300 pages, 14.5 hours, and
  0.4 GB for 2019-20 to 2025-26, against about 14,440 pages and 25 hours for
  the whole dataset.
- The plan's `stats.play_by_play_*` and `features.*` tables do not exist, and
  the measurement no longer needs them.

# Human decisions or resources

All decisions are taken; the card waits on a measurement, not on the owner.

- [x] **Go/no-go** (decided 2026-10-18, revised 2026-11-06 before any result):
      starts only if `F8-009` or, after a no-go there, `F8-019` records a go by
      its fixed rule. Two no-gos close Stage 4: this card is deleted with the
      result recorded in `PREDICTOR_PLAN.md`.
- [x] **Reconstruction source**: our own period-start lineup inference on the
      Basketball Reference pages. No NBA.com pilot in Stage 4 (it would need
      the owner to accept another provider's terms).
- [x] **Lineup gate** (revised 2026-11-06): resolving five names does not prove
      they are the right five, so the gate is reconciliation. A game is left
      out of lineup features, and counted, if a period start does not resolve
      to five per team or a substitution contradicts the lineup. Impact
      features continue only if at most 2 % of published plus-minus lines fail
      to reproduce exactly, on the pilot's in-scope games first and again on
      every acquired game. A game with no real published plus-minus (the 2023
      and 2025 Cup finals) is unverified: reported apart, never a pass.
      Otherwise only lineup-free features continue.
- [x] **Order** (revised 2026-11-06, so nothing is migrated before a result):
      reconstruction on the pilot (offline) → gated acquisition →
      reconciliation of every acquired game → lineup-free features, evaluated
      → regularized impact, evaluated → schema and loader, only if features are
      kept.
- [x] **The measurement runs from the cache** (2026-11-06): features are
      computed from cached pages, with an input fingerprint as in F8-007.
- [x] **Seasons** (2026-11-06): the training seasons of the incumbent's window
      for 2025, plus 2025 and 2026, newest first, one season per batch. With
      `last_5` that is 2019-20 to 2025-26. A longer window reaches back at most
      to 2015-16. 2014-15 is never acquired: it produces no training row
      (`ml/splits.py`).
- [x] **Comparison** (2026-11-06): the incumbent is the best feature set that
      needs no new acquisition, `team-player-pregame-v1` after F8-009's go or
      `team-quarter-pregame-v1` after F8-019's. Its family, window, and
      regularization stay fixed; no grid or folds run on the reduced span. Each
      new set then faces the set selected before it by F8-007's rule on 2025,
      and 2026 is scored once for the record. If reconciliation removes games,
      the incumbent is also reported on that reduced set.
- [x] **Impact comes last** (2026-11-06): lineup-free features test a different
      signal, so their loss does not cancel impact, but impact needs the lineup
      gate. Without availability the model does not know who plays the target
      game, which is where impact should help most, so a loss here is an
      expected outcome, not a reason to tune it.
- [x] **Injuries stay out.**

# Acceptance criteria

To write in `prepare-task` once a go is recorded, by splitting into the order
above. Each piece then gets its own validation commands.

# Impact

- A period-line reader, lineup reconstruction, a gated acquisition command, and
  new feature sets. Schema and loader only if features are kept.
- Serving a play-by-play model adds one request per finished game to F8-008's
  refresh. A promotion card has to weigh that cost; this card does not take it.

# Cross-track impact

- None until Stage 5 exposes player availability in the prediction response.

# Implementation notes

- Possessions are never counted as independent wins (plan Stage 4).
- Proposed pieces, in order: reconstruction with tests and the pilot gate; the
  gated acquisition; lineup-free features and their evaluation; impact and its
  evaluation; schema and loader, created only by a kept result.
- Reconstruction rule: a player with seconds in a period's box started it unless
  their first logged substitution there brings them in. Reuse F8-019's
  period-line reader if that card ran.
- Period minutes are noisier in 2014-15 and 2015-16 (1,582 of the 1,885 games
  with a minutes gap), outside the first batch.
- The first piece replaces the 2026-11-06 probe, which is not in the repository.

# Durable knowledge updates

- `docs/ml/PREDICTOR_PLAN.md` — the Stage 4 play-by-play result, dated.
- `docs/validation/PER_GAME_ACQUISITION_PILOT.md` — the gate measured by real
  code, if it differs from the probe.

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
