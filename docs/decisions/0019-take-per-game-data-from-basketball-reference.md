# ADR 0019 - Take Per-Game Data From Basketball Reference

## Status

Accepted, 2026-09-23, by F8-001. A no-go from the F8-001 pilot
(`docs/validation/PER_GAME_ACQUISITION_PILOT.md`) reopens it.

## Context

Stage 1 of `docs/ml/PREDICTOR_PLAN.md` needs per-game data — schedule, results,
team and player box scores, play-by-play — and proposed NBA.com (stats or CDN
JSON, optionally through `nba_api`) as the candidate primary provider. Four
facts decide the choice:

- **Identity.** `core` is keyed on Basketball Reference identifiers:
  `core.players.basketball_reference_player_id` and Basketball Reference team
  codes in `core.teams` and `core.team_seasons`. Basketball Reference box score
  and play-by-play pages link every player and team by those same identifiers.
  NBA.com uses its own person and team ids; joining them to `core` needs a
  crosswalk, and the plan forbids resolving one by name.
- **Infrastructure.** The one HTTP client, the cache, and the live-scraping
  approval gate are built for Basketball Reference. A second host needs a second
  client path, its own host allow-lists, and a generalized gate — more surface
  on the safety interlock.
- **Terms.** NBA.com's terms of use are the owner's to accept, personally.
  Automated access to Basketball Reference at this project's pace is already
  established practice (3,326 cached pages).
- **Cost.** A second provider would keep the same 6-second floor (F8-001's own
  proposal), so NBA.com is no faster per game. Its real advantages are bulk
  season endpoints and `pbpstats` compatibility.

## Decision

Per-game data comes from Basketball Reference, through the existing client,
cache, limits, and approval gate:

| Data | Page |
|---|---|
| Schedule and results | `/leagues/NBA_<season_end_year>_games[-<month>].html` |
| Team and player box score | `/boxscores/<game_id>.html` |
| Play-by-play | `/boxscores/pbp/<game_id>.html` |

The Basketball Reference game id, `<yyyymmdd>0<home code>`, is the provider's
game id. Team schedule pages (`/teams/<CODE>/<YEAR>_games.html`) are not used:
their cache filenames match the loose team-season pattern of
`cache_inventory.py` and would surface as `missing_metadata` coverage issues.

NBA.com remains a candidate for Stage 4 play-by-play only — possession and
lineup reconstruction with `pbpstats` — behind its own pilot and the owner's
decision on its terms.

## Consequences

- Per-game rows join `core` by identifier. A player missing from `core` — a
  rookie of a season past the archive — is a new Basketball Reference id, never
  an ambiguous mapping; F8-002 decides whether the plan's `*_source_ids`
  tables are still needed.
- Two requests per game at the six-second floor. The pilot measured 6.1–6.3
  seconds per page, so a 1,230-game season is about 2.1 hours of box scores and
  as much again for play-by-play.
- Game type comes from the box score heading: the schedule pages do not mark
  playoff games or the NBA Cup final, which does not count toward the regular
  season.
- `pbpstats` does not read Basketball Reference pages. Possession and lineup
  reconstruction on this play-by-play is either own code or a Stage 4 NBA.com
  pilot.
- The new pages share `data/raw/html/basketball-reference/` with the archive.
  Existing discovery ignores them: `cache_inventory.py` classifies them as
  `unsupported_path`, which every backfill skips, and the stats-coverage
  fingerprint hashes only player pages and valid team-season pages.

## Alternatives Considered

- **NBA.com stats V3 or CDN JSON**: rejected for Stages 1 and 2 — identity
  crosswalk, a second client and gate, and terms only the owner can accept. Kept
  as the Stage 4 play-by-play candidate.
- **`nba_api`**: the same endpoints behind a new runtime dependency, which is a
  `shared` card blocking both tracks.
- **Team game logs** (one page per team-season): far fewer requests for team
  totals, but no player lines and no "did not play" reasons. Worth measuring if
  per-game acquisition proves too slow for Stage 2.
