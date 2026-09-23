# NBA game predictor — research and technical plan

**Status: proposal, pending owner validation.** This is the plan agreed in
research on 2026-09-12, brought into the repository by planning (see `F8-001`,
`F8-002`). Nothing in it is implemented. Where it states a fact about the
database, the fact is dated; code and tests win over this document.

## 1. Conclusion and current state of the database

**The current database is a good player history, but it is not yet ready to
train a reliable game predictor.** It is extended without changing its
structure: games, schedule, and per-game statistics first; players and
play-by-play after.

The product is a regular-season matchup query between current teams: pick a
game — OKC against Chicago, say — and get both teams' win probabilities,
accounting for home court, rest, and whatever information is available at query
time. The interface does not need a full calendar, but the schedule is stored to
compute that context.

### What the database holds

Read-only inspection of the local `nba_postgres` container, database `nba`, on
2026-09-12:

| Item | Result |
|---|---:|
| Applied migration | `0008_drop_raw_schema` (still the head in `alembic/versions/`) |
| Seasons | 26: 1999–2000 to 2024–25 |
| Players | 2,551 |
| Team identities by code/era | 37 |
| Team-seasons | 775 |
| Player-seasons | 12,676 |
| Player-team-season links | 14,344 |
| Regular-season player totals rows | 12,667 |
| Individual games, schedules, game events | no tables exist |

The 37 teams include historical codes; they are not 37 current teams. The nine
player-seasons without regular-season totals match the documented
postseason-only cases. The `*_pbp` tables hold **season summaries** (fouls,
turnovers, plus-minus), not the sequence of plays in each game.

These counts describe the inspected local target on that date. They do not
certify every stored statistic, and the F4E-031 rebuild (applied 2026-09-05) is
already reflected in them.

### What ML is missing

A training row is one game and answers two questions: what did we know
**before** it was played, and who won **after**. End-of-season averages cannot
reconstruct the first question; using them to predict games of that same season
leaks future information.

The history also ends in 2024–25. Before predicting for current teams, recent
games and rosters must be loaded, and a season roster alone does not say who
belonged to a team on a given date.

## 2. Approach

### Team probabilities first, players later

Compare a sequence of models on exactly the same games:

| Model | Information | Role |
|---|---|---|
| Elementary baseline | Historical home win rate | Prove we add anything |
| Elo | Prior results, home court, strength over time | Cheap, competitive reference |
| Regularized logistic regression | Elo, recent form, efficiency, rest | First main candidate |
| Gradient boosting | Same variables and their interactions | Test whether complexity pays |
| Player extension | Expected rotation and individual performance | Adapt to roster changes |
| Play-by-play extension | Adjusted impact, lineups, possessions | Measure further gains |

The first comparison uses scikit-learn, including
`HistGradientBoostingClassifier`, on local CPU. No neural networks or
possession-level simulation at first. This does not presume logistic regression
wins: it fixes a reproducible, cheap comparison before adding complexity. **The
decision is experimental:** keep the model with the best probabilities on later
seasons at the lowest justifiable maintenance cost.

References, not targets: ESPN BPI (team strength plus home, rest, travel);
FiveThirtyEight's forecast archive; NBA Forecast Lab (Elo vs logistic vs XGBoost
with temporal splits, a self-reported ~68.9% in 2025–26, not reproduced here);
Migliorati 2021 and Rios et al. 2025, whose differing data and evaluation do not
yield an algorithm ranking.

- https://www.espn.com/nba/story/_/id/13984129/what-espn-nba-basketball-power-index
- https://github.com/fivethirtyeight/data/blob/master/nba-forecasts/README.md
- https://github.com/seungminnam/nba-forecast-lab
- https://arxiv.org/html/2111.09695v1 · https://arxiv.org/pdf/2512.08591

### Initial variables

Home-minus-away differences in:

- pre-game Elo;
- offensive, defensive, and net efficiency;
- pace and point margin;
- shooting efficiency, turnovers, offensive rebounding, free-throw rate;
- last 5, 10, and 20 games plus the season-to-date aggregate;
- rest days, back-to-backs, games in the last seven days;
- amount of history available, so two games are distinguishable from forty.

Rates are computed from accumulated numerators and denominators, never by
averaging per-game percentages. Opponent-strength adjustment is an extension;
travel distance, time zones, and coaching continuity come after the basics are
proven.

### Individual statistics

Do not invent another PER — the database already stores it and other advanced
metrics. Evaluate offensive and defensive performance separately, expected
minutes and rotation continuity, shooting volume and efficiency, creation,
turnovers, rebounding, and the age and sample size of the information. Team
aggregation is weighted by **expected minutes**, not a flat mean over the
roster. A versioned 0–100 rating may be added for presentation; **it is not a
win probability.** NBA 2K ratings are inspiration for multi-attribute player
profiles only, not model input.

### The notebook `internet_proyect_tocheck.ipynb`

Reusable ideas: pre-game Elo, ten-game rolling means, team vs individual model
comparison. Not transferable as is: it depends on Synergy Sports and an old
Colab environment, splits train/test randomly, reuses the test set to choose
between alternatives, favors binary accuracy over probability quality, and its
individual model aggregates players already known to have appeared in the game.
Its stored ~67% results are not reproduced and do not support its claim of a
universal 70% ceiling.

### Play-by-play: yes, for a specific purpose

Included, but **the first predictor does not wait for its full acquisition.**
Its value is lineup and stint performance, teammate- and opponent-adjusted
offensive and defensive impact (Fearnhead and Taylor, 2010,
https://arxiv.org/abs/1008.0705), possession and shot profiles, and rotation
differences. Sharing the floor does not prove one player guarded another;
matchup questions may need tracking data. Pair and lineup effects have small
samples and need regularization.

### Candidate sources

| Source | Proposed use | Limitation |
|---|---|---|
| NBA.com (stats / CDN endpoints, optionally via `nba_api`) | Schedule, results, box scores, events | Validate access and coverage; endpoints change; terms of use to confirm |
| `pbpstats` | Offline possession and lineup interpretation | Check compatibility with the acquired format |
| Basketball Reference | Continuity with the existing history; cross-check | Existing six-second floor; automated access is not implied by a public page |
| Third-party public archives | Could reduce historical acquisition | Require provenance, coverage, and clear terms |

`nba_api` documents `PlayByPlayV2` as deprecated in favor of `PlayByPlayV3`,
plus an adapter for the NBA CDN play-by-play JSON. Stathead and Basketball
Reference play-by-play are distinct products and access paths.

## 3. Proposed database extension

The layers stay: identities in `core`, sporting observations in `stats`, own
computations in `features`, models in `ml`. Original documents stay in the file
cache; the `raw` schema dropped by migration 0008 is not reintroduced.

### Games, schedule, and players

| Proposed table | Grain and content |
|---|---|
| `core.games` | One game: stable public id, season, competition type, home and away team-seasons, scheduled date, neutral site, status |
| `core.game_schedule_versions` | One schedule observation: game, scheduled date, status, source, observed-at |
| `core.game_source_ids` | Internal game ↔ provider id |
| `core.player_source_ids` | Internal player ↔ external ids |
| `core.team_season_source_ids` | Team mapping per provider and season, respecting existing historical codes |
| `core.roster_observations` | Observed player–team membership, observation date, validity when published |
| `stats.team_game_totals` | One row per game and team: points, minutes, basic box-score counters |
| `stats.player_game_totals` | One row per game and player: team, participation, starter, minutes, basic counters |

Rules:

- Home and away differ and both belong to the game's season.
- A valid final game has two team rows and a consistent result.
- A player who did not play is never confused with one who played and recorded
  zeros.
- Source ids are stored as text, keeping leading zeros.
- Ambiguous mappings are set aside for review, never resolved by name alone.
- Postponements change the current schedule version and keep earlier
  observations.
- NBA/Basketball Reference integration never redefines existing public
  identities and never infers `franchise_id`.

### Play-by-play events

| Proposed table | Grain and content |
|---|---|
| `stats.play_by_play_feeds` | One version of a game feed: provider, hash, cache, acquisition/publication dates, parser version |
| `stats.play_by_play_events` | One event in that feed: original id and order, period, clock, type/subtype, team, score, description |
| `stats.play_by_play_participants` | Event participants and observed role: shooter, assister, rebounder, substitution |

The event key includes the feed version; **the clock is never a unique key.**
Original event codes are kept beside their normalized class, unknown events stay
recoverable, and unresolved actors keep their external id and are flagged. Each
source correction becomes a content-identified version; providers are never
mixed in one reconstruction.

### Derived data and models

| Proposed table | Content |
|---|---|
| `features.possessions` | Reconstructed possessions, offense, bounds, points, algorithm version |
| `features.lineup_stints` | Stable-lineup stretches, duration, score, reconstruction quality |
| `features.lineup_stint_players` | Players of each team in each stint |
| `features.team_game_snapshots` | Pre-game variables, cutoff instant, definition version |
| `features.player_impact_snapshots` | Estimated player impact, sample used, cutoff date |
| `ml.model_versions` | Local artifact, configuration, variables, training window, metrics |
| `ml.predictions` | Forecasts logged by local processes, with model, cutoff, and inputs |

An incomplete reconstruction is never filled with invented players; it is
excluded from metrics that need ten identified participants. Indexes cover
team+date, player+date, game+sequence, and game+cutoff; unique keys make every
load idempotent.

### Injuries: designed, deferred

No permanent `injured` boolean on `core.players`. A future availability
observation table links player and, when known, game: status, reason, source,
published/observed time. A missing player's effect is computed by redistributing
minutes, not by subtracting a fixed amount. Until then predictions are labeled
as not adjusted for confirmed absences.

## 4. Stages

### Stage 1 — prove acquisition is feasible (`F8-001`)

A pilot of 30 games spread across seasons and edge cases: overtime, simultaneous
substitutions, score reviews, incomplete data. NBA.com is the candidate primary
provider; the endpoint choice (stats V3 vs CDN) follows coverage and consistency
in the pilot. If neither satisfies the requirements, large-scale acquisition
stops and the failure is documented.

Measure identity coverage and resolution; final score vs box score vs events
reconciliation; requests, bytes, and wall time per game; offline compatibility
with `pbpstats`. Acquisition keeps the cache, provenance, per-provider limits,
and the existing explicit approval. Parsers and tests stay offline. Basketball
Reference keeps its six-second floor and stop-on-429.

Arithmetic estimate only: 1,230 requests six seconds apart take ~2.05 h; two
resources per game, ~4.1 h, excluding errors, latency, and extra waits.

### Stage 2 — game dataset and first predictor (`F8-002` onwards)

Acquire schedule, results, and box scores from 2014–15 to the last complete
season, plus the current season when relevant. Team model first; per-game
player statistics load in this stage to prepare the next. The training unit is
one game; the target is home win including overtime. Preseason, All-Star,
play-in, and playoffs are excluded; in-season tournament games that count as
regular season are included once. Evaluation reconstructs a forecast **24 hours
before tip-off**; interactive queries use the real query time and show their
lead time. Horizons are never mixed when reporting.

### Stage 3 — temporal evaluation and selection

- Last complete season: final test.
- Second-to-last: calibration and final selection.
- Earlier seasons: training and rolling temporal validation.

Compare three-season, five-season, and full-period training windows. Scaling,
imputation, and variable selection are fitted inside each training split. Every
variable uses only games finished before the cutoff. Retrospectively downloaded
history distinguishes reconstruction from final results vs strict replay of what
was published then; `fetched_at` is never presented as historical availability.

| Measure | Question |
|---|---|
| Log loss (primary) | Are the probabilities useful, penalizing confident errors? |
| Brier score | Overall probabilistic error |
| Calibration curve with sample sizes | Do ~70% games win ~70% of the time? |
| Accuracy | How many winners do we pick? |
| ROC-AUC | Do we order favorites sensibly? |

Calibration is fitted on data separate from training and kept only if it
improves later validation
(https://scikit-learn.org/stable/modules/calibration.html). Changes are compared
by metric differences with temporal-block intervals; indistinguishable results
keep the simpler model. The final test season is never used for selection.

### Stage 4 — players and play-by-play

Add pre-game rotation and individual variables first, then play-by-play:
possessions, team profiles, regularized impact. Compare team → team + players →
team + players + possessions on the same games; if play-by-play coverage shrinks
the sample, also report the basic model on that sample. Millions of events do
not change that the target has one result per game; possessions are never
counted as independent wins.

### Stage 5 — local query (`app` track)

`GET /api/v1/games` (filter by date and teams) and
`GET /api/v1/games/{game_id}/prediction`: teams, scheduled start, complementary
probabilities, favorite, data date, model version, and whether player
availability is included. The API reads prepared data and runs local inference;
it never scrapes, trains, or writes. Missing required data yields an explicit
"forecast unavailable" with a reason — never a 50–50 stand-in. This reaches the
`app` track as a handoff card recorded in `tasks/CROSS_TRACK.md`.

### Acceptance tests across stages

- Duplicates, postponements, and corrections never produce repeated games.
- Sums and scores reconcile, separating team statistics that belong to no
  player.
- Overtime, substitutions, and same-clock events are processed correctly.
- Changing any data after the cutoff never changes an earlier forecast.
- No minutes, participants, or results of the target game are pre-game inputs.
- Probabilities lie in `[0, 1]` and sum to one.
- The same model and data version reproduce the forecast.
- Models are compared on the same dates, games, and horizon.
- Migrations are tested only on disposable PostgreSQL; parsers and API are
  validated with offline fixtures.

## 5. Fixed decisions and limits

- **Goal:** win probabilities, not profit against betting odds.
- **First competition:** NBA regular season.
- **Use:** current teams and upcoming games picked by the user.
- **Execution:** local, favoring free sources.
- **First model:** Elo vs logistic regression vs gradient boosting.
- **Play-by-play:** included, after a pilot, with its predictive value measured.
- **Injuries:** designed, not yet implemented.
- **2K:** inspiration for profiles; its ratings are not model input.
- **Success:** better probabilities than the baselines under temporal
  evaluation, not a promised percentage.
- **Investment order:** recent per-game data → reliable evaluation → players →
  play-by-play → availability and refinements.

## 6. Workflow constraints (added in planning)

- Everything up to Stage 4 is `data` track work (ADR 0018); Stage 5 is `app`.
- A new runtime dependency (`nba_api`, `pbpstats`, `scikit-learn`) changes
  `pyproject.toml`/`uv.lock` and is therefore a `shared` card, which blocks both
  tracks. `httpx` is already a dependency, so a pilot can fetch without one.
- The live-scraping approval gate (`--owner-approved`, approved manifests,
  acquisition guards) is a safety interlock. A second provider extends it; it
  never weakens or bypasses it. Every live run needs the owner's direct
  instruction.
- New migrations are applied to the persistent `nba` database only from merged
  `origin/main`, with the owner's approval.
