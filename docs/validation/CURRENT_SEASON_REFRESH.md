# Current-Season Refresh

One gated, bounded command refreshes the season in progress
(`CURRENT_SEASON_END_YEAR`, 2027): its schedule pages, its 30 team pages once,
and the box scores of games finished since the last refresh. Built in F8-013;
the runs belong to F8-008, each on the owner's direct instruction.

## What a run fetches

A standing `current_season_refresh` manifest approves a **rule**, not a URL
list. One run, in this order, each phase planned from the snapshots the previous
phase just wrote:

| Phase | Pages | Written to |
|---|---|---|
| `season` | `/leagues/NBA_2027_games.html`, every run | `SnapshotCache` (`SCRAPER_SNAPSHOT_DIR`) |
| `month` | the months the latest season snapshot links: the month of `--as-of`, the next one, any earlier month whose latest snapshot shows a game dated before `--as-of` without a score, and any month never fetched | `SnapshotCache` |
| `team` | `/teams/<code>/2027.html` for the 30 teams the month snapshots list, only while a team has no snapshot | `SnapshotCache` |
| `box_score` | `/boxscores/<game_id>.html` of every game with a score in the latest month snapshots and no archived box score | `HtmlCache` (`SCRAPER_CACHE_DIR`) |

Ceilings per run: 20 schedule pages (season page included), 30 team pages, 150
box scores, 10 requests/minute. A phase whose plan is larger **stops the run**
(`plan_refused`); nothing is trimmed. A team count other than 30 also stops it.

`--as-of YYYY-MM-DD` is required and is the only date the rule uses: the
command never reads the clock. It must fall between 2026-08-01 and 2027-10-31.

A daily refresh is about 3 schedule pages and 10–15 box scores (~2 minutes at
six seconds a request); the first one also takes 7 month pages and 30 team
pages.

## Draft and approve the manifest (once per season)

1. Write the draft (offline; refuses to replace an existing file):

   ```bash
   uv run python -c "from datetime import UTC, datetime; from nba_data.scraping.current_season_manifest import write_draft_current_season_manifest as w; print(w(datetime.now(UTC)))"
   ```

   It lands at `reports/current-season/NBA_2027_current-season-refresh.draft.json`
   with the ceilings at their maximum, `status: draft` and
   `approved_by_owner: false`.

2. Review it offline:

   ```bash
   uv run nba-data acquisition dry-run-current-season reports/current-season/NBA_2027_current-season-refresh.draft.json --as-of 2026-11-07
   ```

3. The owner approves by copying it into `tasks/manifests/` (F8-008) with
   `status: approved`, `approved_by_owner: true`, a timezone-aware
   `approved_at`, and an `approval_basis`. Ceilings may be lowered, never raised.

The approval does not authorize a run. Each run needs both flags **and** the
owner's direct, current instruction (`AGENTS.md`, critical actions).

## One refresh

Offline plan first. The dry run shows the season page, the month and team pages
from the latest snapshots, and box scores only for scores already seen; the run
re-plans box scores from the month pages it fetches.

```bash
uv run nba-data acquisition dry-run-current-season tasks/manifests/<approved>.json --as-of YYYY-MM-DD
```

Then, on the owner's instruction:

```bash
uv run nba-data acquisition acquire-current-season tasks/manifests/<approved>.json --as-of YYYY-MM-DD --owner-approved --execute-approved-manifest --output reports/current-season/refresh-YYYY-MM-DD.json
```

`--max-fetches N` ends the run cleanly after N live requests.
It does not split a plan above a manifest ceiling. Every rerun fetches the
season and selected month pages again, so a budget spent entirely on those
pages cannot advance to team pages or box scores. Choose a budget larger than
that recurring schedule cost; check `completed` and `stopped_at_phase` in the
report even when the command exits 0.

Refusals, all before any request: either flag missing (exit 1, before the
manifest is read); a draft, another season, a ceiling above the maximum, the
placeholder `SCRAPER_USER_AGENT`, a pace above 10/minute or above the
manifest's, or a malformed `--as-of` (exit 2).

## The report

Like F8-004's, with a `phase` on every entry: `planned` per phase (`null` for a
phase the run did not reach), `fetched`, `live_request_count`, `completed`,
`stopped_reason` (`rate_limited`, `failed`, `plan_refused`, `max_fetches`),
`stopped_at_phase`, `stopped_at_url`, `retry_after_seconds` and
`error_details`. Exit code 1 on any stop except `max_fetches`.

## Resume

Rerun the same command. Box scores are cache-first, so the archived ones are not
requested again; team pages with a snapshot are skipped; schedule pages are
fetched again as new snapshots, which is the point of the rule.

- **429:** wait at least `retry_after_seconds`, then rerun on a new instruction.
- **`plan_refused`:** read `error_details`. A ceiling exceeded means the backlog
  of box scores is larger than one run allows; see Known limitations.
- **`failed`:** fix the cause in `error_details`; a snapshot write killed half
  way is listed by `SnapshotCache.incomplete_writes` (ADR 0022).

## Known limitations

- A backlog above the manifest's box-score ceiling (at most 150) cannot be
  cleared by this command. Keep the ceiling and refusal rule intact; F8-020
  designs a separate bounded catch-up path before F8-008 starts. The Stage 2
  explicit-URL workflow accepts seasons only through 2026 and cannot be used
  unchanged for 2027. The actual backlog must be counted from snapshots;
  a date alone does not establish that the ceiling has been exceeded.
- Schedule responses must parse without issues and contain only game dates
  inside the current season window before a snapshot is published. A rejected
  response leaves the previous snapshot usable for the next run.
- Team and box-score bodies currently receive only a generic HTML check. A
  200 HTML error page could satisfy cache coverage; F8-021 defines page-type
  and identity validation before publication.
- Postponed rows without a score keep their month refetched on every run until
  the page drops or scores them.
