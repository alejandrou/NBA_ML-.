# System Design

## Target Architecture

```text
Scraper batch/job
  -> raw HTML cache
  -> parsers
  -> normalizers
  -> validators
  -> idempotent loaders
  -> PostgreSQL
  -> features/metrics
  -> FastAPI
  -> Next.js
```

## Target Python Layout

```text
src/nba_data/
  config/
  scraping/
    client.py
    cache.py
    snapshot_cache.py
    parsers/
    normalizers/
    loaders/
  db/
    base.py
    session.py
    models/
    repositories/
  features/
  validation/
  cli/
```

Future app split:

```text
apps/
  scraper/
  api/
  web/
```

The web frontend does not wait for this split: ADR 0019 places it in `web/` at
the repository root.

## Responsibilities

- Scraper jobs plan URLs and orchestrate work.
- The HTTP client is the only place for real Basketball Reference requests.
- Cache stores raw HTML as `.html.gz`, each body optionally accompanied by a
  `<body>.html.gz.meta.json` provenance sidecar (`fetched_at`, `http_status`,
  `final_url`). The sidecar is written only for pages fetched after F4E-028;
  it is an index, not an invariant, and reading a body never requires it.
- The cache has two roots (ADR 0022). The **archive cache**
  (`SCRAPER_CACHE_DIR`, `data/raw/html`, `HtmlCache`) holds one body per URL
  and never overwrites it. The **snapshot cache** (`SCRAPER_SNAPSHOT_DIR`,
  `data/raw/snapshots`, `scraping/snapshot_cache.py`) holds pages that still
  change — the `CURRENT_SEASON_END_YEAR` league schedule pages and team-season
  pages, declared by `is_mutable_page` — as one timestamped snapshot per fetch,
  `<host>/<slug>-<sha256[:16]>/<fetched_at UTC>.html.gz` with a required
  sidecar. Nothing is replaced; readers take the latest snapshot and ignore any
  archive copy of a mutable page. Settings reject overlapping roots, so the
  archive inventory and backfills never see a snapshot. Box scores are
  immutable and stay in the archive cache.
- Parsers are pure functions from HTML to structured data.
- Normalizers convert raw parsed rows into canonical shapes.
- Validators check row counts, keys, ranges, and historical missing metrics.
- Loaders write idempotently to PostgreSQL.
- API reads processed data only and never scrapes live.
- Frontend consumes the API, not the database directly.

## Loader Invariants

The pipeline boundary is fixed:

```text
cached HTML -> pure parser -> normalizer -> validator -> idempotent loader
```

- Cached HTML is the raw source of truth for repeatable parsing.
- Parsers receive HTML strings and touch neither network nor database.
- Normalizers convert parser rows into canonical records with explicit source
  metadata.
- Validators check row shape, required identifiers, duplicates, and domain rules
  before any database write.
- Loaders write only validated records and must be safe to rerun: check natural
  keys before writing, use portable select-then-insert/update logic, and leave
  transaction control to the caller.

### Core Natural Keys

The keys loaders match on before writing. Changing one changes idempotency:

| Table | Natural key |
|---|---|
| `core.seasons` | `(league, season_year)` |
| `core.team_aliases` | `(team_id, abbreviation, from_season_year, to_season_year)` |
| `core.players` | `basketball_reference_player_id` |
| `core.games` | `basketball_reference_game_id` (`<yyyymmdd>0<home code>`, e.g. `202310240DEN`) |
| `stats.team_game_totals` | `(game_id, team_season_id)`; also unique `(game_id, is_home)` |
| `stats.player_game_totals` | `(game_id, player_id)` |

A row whose stable player identifier is unavailable is rejected or quarantined,
never matched by name — `player_name` is not a stable key.

### Game Grain

Revision `0009_games_and_box_scores` adds the per-game grain the team predictor
reads. `nba-data backfill games` writes it (below).

- `core.games` holds a game's identity, schedule, and status (`scheduled`,
  `final`, `postponed`) — never its result. Both teams reference
  `core.team_seasons` through composite keys on `(id, season_id)`, so they
  always belong to the game's own season.
- `stats.team_game_totals` holds one row per side. The final score is its `pts`,
  stored only there.
- `stats.player_game_totals` holds one row per player per game, absences
  included. It references `core.players` directly and the team-season through
  the team total, avoiding `core.player_team_seasons` because inactive-only
  and current-season players have no player-season row. Its composite foreign
  key means a player line exists only for a team whose total for that game is
  loaded.
- The check conditions are frozen in the revision and pinned to the models and
  the box score parser's constants by `tests/unit/test_game_models.py`.
  `docs/domain/BUSINESS_RULES.md` lists the invariants, including the
  cross-table ones the loader must enforce itself.

### Offline game load

```text
cached league schedule pages -> select_season_games (F8-004 rule)
cached box score page        -> parse_box_score_page
                             -> load_game: gates, then upserts      (one transaction per game)
                             -> derive_neutral_sites (second pass over the season)
                             -> one JSON report per season
```

`nba-data backfill games --execute-approved-games-backfill --season <end year> [--season ...] [--output <dir>]
[--require-complete]` reads only the cache: no HTTP client is constructed, and a
box score that is not cached is reported as `missing_box_score`. Each selected
game is gated and written by `scraping/loaders/games.py` and committed on its
own, so a quarantined or failing game writes nothing while the others load. The
report gives, per season, `expected`, `loaded`, `unchanged`,
`missing_box_score`, `quarantined` (by reason, with game ids), `warnings`,
`players_created`, `neutral_games`, and `game_types`. The command exits
non-zero when any game is quarantined or fails, when a season selects no game,
and, with `--require-complete`, when any box score is missing. A rerun over the
same cache reports every game `unchanged` and writes nothing.

The approval flag is required before an engine is constructed. `--output`
names a directory, including for a single season. Corrupt schedule caches fail
selection; corrupt box-score caches fail that game and let the others load.
Neutral-site inference waits until every selected game exists in the database;
partial loads report `neutral_site_deferred` and leave the flags unchanged.

Like every write path, it writes to the database `DATABASE_URL` names. Loading
the persistent `nba` database is an owner-approved step (F8-018), run from
merged `origin/main` once revision 0009 is applied there.

`validate game-pilot --database-identities` reads player and NBA team-season
keys from `DATABASE_URL`, including players created only from inactive lists.
Without that option, the pilot stays cache-only. Pages always come from cache.

The disposable PostgreSQL lane (`bash scripts/validate_database.sh`) bounds
connections and each child step, and connects to `postgres` for administration.
It uses IPv4 for `localhost`, matching the compose port binding and avoiding
Windows IPv6 fallback delays. Explicit connection URL options are preserved.
On Windows, use Git Bash; the Windows `System32/bash.exe` requires WSL.

## Planned Direction

Work after the read-only API, in order:

**Web frontend** — `web/`, consuming the API only. It must never query the
database directly or trigger scraping. ADR 0008 chose the stack, ADR 0019 scopes
v1, and `WEB_ARCHITECTURE.md` specifies it.

**Generated metrics, rankings, and OVR** — stored in the `features` schema,
never mixed into cached raw source material, `core`, or official `stats` tables.
Formula versions are recorded, assumptions and limitations documented, and
metric generation must be leakage-safe and must never scrape live.

Concrete work is tracked as cards in `tasks/backlog/`, not as phase documents.
