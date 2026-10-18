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
  - docs/decisions/0020-take-per-game-data-from-basketball-reference.md
  - src/nba_data/scraping/parsers/play_by_play.py
validation: []
critical_actions:
  - Live acquisition of ~14,440 play-by-play pages (~25 hours) through a gated command copied from F8-004's — the owner's direct instruction per batch.
  - Applying the play-by-play schema to the persistent nba database.
---

# Goal

Stage 4, step two: possessions, team profiles, and regularized impact from
play-by-play, kept only if they beat the team + player model on the same games.

# Evidence and current state

- The parser exists (`parsers/play_by_play.py`); 29 of 30 pilot games
  reconcile. Lineups between periods are not logged (pilot finding 12), and
  `pbpstats` does not read these pages (ADR 0020).
- Cost: ~14,440 pages, ~25 hours, ~0.7 GB.
- The plan's `stats.play_by_play_*` and `features.*` tables do not exist.

# Human decisions or resources

All decisions are taken; the card waits on a measurement, not on the owner.

- [x] **Go/no-go** (decided 2026-10-18): starts only if `F8-009` records a go
      by its fixed rule. A no-go closes Stage 4 and this card is deleted with
      the result recorded in `PREDICTOR_PLAN.md`.
- [x] **Reconstruction source**: our own period-start lineup inference on the
      Basketball Reference pages. No NBA.com pilot in Stage 4 (it would need
      the owner to accept another provider's terms). Measured first on the
      pilot's 30 games: if more than 2 % of period starts cannot be resolved to
      five players per team, the impact features (which need lineups) are
      dropped and only lineup-free possession features continue.
- [x] **Order**: inference measured on the 30 pilot games (offline) →
      schema → gated acquisition → possessions and team profiles →
      regularized impact → evaluation by F8-007's rule.
- [x] **Injuries stay out.**

# Acceptance criteria

To write in `prepare-task` once F8-009 records a go, by splitting into the
order above. Each piece then gets its own validation commands.

# Impact

- Play-by-play schema and loader, a gated acquisition command, new features.

# Cross-track impact

- None until Stage 5 exposes player availability in the prediction response.

# Implementation notes

- Possessions are never counted as independent wins (plan Stage 4).

# Durable knowledge updates

- `docs/ml/PREDICTOR_PLAN.md` — the Stage 4 play-by-play result, dated.

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
