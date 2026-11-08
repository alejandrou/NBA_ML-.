"""Offline planning of one current-season refresh (F8-013).

Every URL comes from the approved rule (`current_season_manifest.py`) applied to
the latest snapshots (`SnapshotCache`) and the archive cache (`HtmlCache`);
nothing is fetched or written here, and no clock is read: the run's date is the
owner's `--as-of`.

- **Schedule pages.** The season page, every run. The month pages its latest
  snapshot links: the month of `as_of`, the next one, any earlier month whose
  latest snapshot shows a game dated before `as_of` without a score (a late
  score, or a postponed row), and any month never fetched.
- **Team pages.** The season's 30 team pages, only while they have no snapshot.
  The teams are the ones the latest month snapshots list; any other count is an
  error, so a missing month or a malformed page never shrinks the set.
- **Box scores.** Games with a score and a box-score link in the latest month
  snapshots, and no box score in the archive cache.

A plan larger than the manifest's ceiling raises `CurrentSeasonPlanningError`;
it is never trimmed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.current_season_manifest import CurrentSeasonManifest
from nba_data.scraping.game_pilot_manifest import (
    BASE_URL,
    MONTHS,
    box_score_url,
    league_schedule_url,
)
from nba_data.scraping.game_season_manifest import is_schedule_month
from nba_data.scraping.parsers.league_schedule import (
    ParsedLeagueSchedule,
    parse_league_schedule_page,
)
from nba_data.scraping.snapshot_cache import CURRENT_SEASON_END_YEAR, SnapshotCache

PHASE_SEASON = "season"
PHASE_MONTH = "month"
PHASE_TEAM = "team"
PHASE_BOX_SCORE = "box_score"
PHASES = (PHASE_SEASON, PHASE_MONTH, PHASE_TEAM, PHASE_BOX_SCORE)

TEAMS_PER_SEASON = 30

# Months from August on belong to the calendar year before the season's end
# year. A sanity bound for `as_of` too, never a way to derive the season.
_FIRST_SEASON_MONTH = 8
_SEASON_WINDOW_START = (8, 1)
_SEASON_WINDOW_END = (10, 31)


class CurrentSeasonPlanningError(ValueError):
    """Raised when a refresh cannot be planned safely from the snapshots."""


@dataclass(frozen=True)
class PlannedPage:
    phase: str
    url: str
    reason: str
    month: str | None = None
    team: str | None = None
    game_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "phase": self.phase,
            "url": self.url,
            "month": self.month,
            "team": self.team,
            "game_id": self.game_id,
            "reason": self.reason,
        }


def require_as_of_in_season(as_of: date, season_end_year: int = CURRENT_SEASON_END_YEAR) -> None:
    start = date(season_end_year - 1, *_SEASON_WINDOW_START)
    end = date(season_end_year, *_SEASON_WINDOW_END)
    if not start <= as_of <= end:
        msg = (
            f"--as-of {as_of.isoformat()} is outside the {season_end_year} season "
            f"({start.isoformat()} to {end.isoformat()})"
        )
        raise CurrentSeasonPlanningError(msg)


def season_page_url(season_end_year: int = CURRENT_SEASON_END_YEAR) -> str:
    return league_schedule_url(season_end_year)


def team_page_url(team: str, season_end_year: int = CURRENT_SEASON_END_YEAR) -> str:
    return f"{BASE_URL}/teams/{team}/{season_end_year}.html"


def month_calendar(slug: str, season_end_year: int) -> tuple[int, int]:
    """The (year, month) a schedule month slug names within its season."""

    if not is_schedule_month(slug):
        msg = f"Unknown schedule month {slug!r}"
        raise CurrentSeasonPlanningError(msg)
    name, _, explicit_year = slug.partition("-")
    month = MONTHS.index(name) + 1
    if explicit_year:
        return int(explicit_year), month
    return (season_end_year - 1 if month >= _FIRST_SEASON_MONTH else season_end_year), month


def latest_schedule(snapshots: SnapshotCache, url: str) -> ParsedLeagueSchedule | None:
    """The parsed latest snapshot of a schedule page, or None if never fetched."""

    snapshot = snapshots.latest(url)
    if snapshot is None:
        return None
    return validate_schedule_page(snapshot.body, url)


def validate_schedule_page(html: str, url: str) -> ParsedLeagueSchedule:
    """Check a schedule before publishing it or using it to authorize more URLs."""

    parsed = parse_league_schedule_page(html)
    if parsed.issues:
        codes = sorted({issue.code for issue in parsed.issues})
        msg = f"The schedule page {url} does not parse cleanly: {', '.join(codes)}"
        raise CurrentSeasonPlanningError(msg)
    for game in parsed.games:
        try:
            require_as_of_in_season(game.game_date)
        except CurrentSeasonPlanningError as exc:
            msg = f"The schedule page {url} contains a game outside the current season: {game.game_date}"
            raise CurrentSeasonPlanningError(msg) from exc
    return parsed


def linked_months(snapshots: SnapshotCache, season_end_year: int) -> tuple[str, ...] | None:
    """The month slugs the latest season snapshot links, or None before the first one."""

    url = season_page_url(season_end_year)
    season_page = latest_schedule(snapshots, url)
    if season_page is None:
        return None
    if not season_page.month_links:
        msg = f"The latest snapshot of {url} links no month pages"
        raise CurrentSeasonPlanningError(msg)
    unknown = [month for month in season_page.month_links if not is_schedule_month(month)]
    if unknown:
        msg = f"The latest snapshot of {url} links unknown months: {unknown}"
        raise CurrentSeasonPlanningError(msg)
    return season_page.month_links


def plan_season_page(season_end_year: int) -> PlannedPage:
    return PlannedPage(
        phase=PHASE_SEASON,
        url=season_page_url(season_end_year),
        reason="Season page, every run: its month links name the month pages.",
    )


def plan_month_pages(
    manifest: CurrentSeasonManifest,
    *,
    snapshots: SnapshotCache,
    as_of: date,
) -> tuple[PlannedPage, ...] | None:
    """The month pages to refetch, or None while the season page has no snapshot.

    Raises when the season page plus these months exceed the schedule ceiling.
    """

    season = manifest.season_end_year
    months = linked_months(snapshots, season)
    if months is None:
        return None

    as_of_month = (as_of.year, as_of.month)
    next_month = (as_of.year + as_of.month // 12, as_of.month % 12 + 1)
    planned: list[PlannedPage] = []
    for month in months:
        url = league_schedule_url(season, month)
        page = latest_schedule(snapshots, url)
        calendar = month_calendar(month, season)
        reason: str | None
        if page is None:
            reason = "Never fetched."
        elif calendar == as_of_month:
            reason = f"The month of --as-of {as_of.isoformat()}."
        elif calendar == next_month:
            reason = f"The month after --as-of {as_of.isoformat()}."
        elif calendar < as_of_month and (unscored := _unscored_before(page, as_of)):
            reason = (
                f"Its latest snapshot shows {len(unscored)} game(s) dated before "
                f"{as_of.isoformat()} without a score: {', '.join(unscored[:5])}."
            )
        else:
            reason = None
        if reason is not None:
            planned.append(PlannedPage(phase=PHASE_MONTH, url=url, month=month, reason=reason))

    schedule_pages = 1 + len(planned)
    if schedule_pages > manifest.max_schedule_pages:
        msg = (
            f"The refresh would fetch {schedule_pages} schedule pages, above the manifest's "
            f"ceiling of {manifest.max_schedule_pages}; nothing is trimmed"
        )
        raise CurrentSeasonPlanningError(msg)
    return tuple(planned)


def plan_team_pages(
    manifest: CurrentSeasonManifest,
    *,
    snapshots: SnapshotCache,
) -> tuple[PlannedPage, ...] | None:
    """The season's team pages without a snapshot, or None until every month is fetched."""

    season = manifest.season_end_year
    month_pages = _latest_month_pages(snapshots, season)
    if month_pages is None or any(page is None for page in month_pages.values()):
        return None

    teams: set[str] = set()
    for page in month_pages.values():
        if page is None:  # excluded above; this keeps mypy honest
            continue
        for game in page.games:
            teams.update((game.visitor_code, game.home_code))
    if len(teams) != TEAMS_PER_SEASON:
        msg = (
            f"The latest month snapshots list {len(teams)} teams, not {TEAMS_PER_SEASON}: "
            f"{sorted(teams)}"
        )
        raise CurrentSeasonPlanningError(msg)

    planned = tuple(
        PlannedPage(
            phase=PHASE_TEAM,
            url=team_page_url(team, season),
            team=team,
            reason="Team page without a snapshot.",
        )
        for team in sorted(teams)
        if snapshots.latest(team_page_url(team, season)) is None
    )
    if len(planned) > manifest.max_team_pages:
        msg = (
            f"The refresh would fetch {len(planned)} team pages, above the manifest's "
            f"ceiling of {manifest.max_team_pages}; nothing is trimmed"
        )
        raise CurrentSeasonPlanningError(msg)
    return planned


def plan_box_scores(
    manifest: CurrentSeasonManifest,
    *,
    snapshots: SnapshotCache,
    archive: HtmlCache,
) -> tuple[PlannedPage, ...]:
    """Box scores of scored games in the latest month snapshots that are not archived."""

    season = manifest.season_end_year
    month_pages = _latest_month_pages(snapshots, season) or {}
    seen: dict[str, str] = {}
    planned: list[PlannedPage] = []
    for month, page in month_pages.items():
        if page is None:
            continue
        for game in page.games:
            if game.game_id is None:
                continue
            if game.game_id in seen:
                msg = (
                    f"Game {game.game_id} is listed on both the {seen[game.game_id]} "
                    f"and {month} snapshots"
                )
                raise CurrentSeasonPlanningError(msg)
            seen[game.game_id] = month
            if not game.played:
                continue
            url = box_score_url(game.game_id)
            if archive.exists(url):
                continue
            planned.append(
                PlannedPage(
                    phase=PHASE_BOX_SCORE,
                    url=url,
                    month=month,
                    game_id=game.game_id,
                    reason=(
                        f"{game.game_date.isoformat()} {game.visitor_code} at {game.home_code}, "
                        f"scored on the latest {month} snapshot"
                    ),
                )
            )

    if len(planned) > manifest.max_box_scores:
        msg = (
            f"The refresh would fetch {len(planned)} box scores, above the manifest's "
            f"ceiling of {manifest.max_box_scores}; nothing is trimmed"
        )
        raise CurrentSeasonPlanningError(msg)
    return tuple(planned)


def _latest_month_pages(
    snapshots: SnapshotCache,
    season_end_year: int,
) -> Mapping[str, ParsedLeagueSchedule | None] | None:
    months = linked_months(snapshots, season_end_year)
    if months is None:
        return None
    return {
        month: latest_schedule(snapshots, league_schedule_url(season_end_year, month))
        for month in months
    }


def _unscored_before(page: ParsedLeagueSchedule, as_of: date) -> list[str]:
    return [
        f"{game.game_date.isoformat()} {game.visitor_code} at {game.home_code}"
        for game in page.games
        if game.game_date < as_of and not game.played
    ]


__all__ = [
    "PHASES",
    "PHASE_BOX_SCORE",
    "PHASE_MONTH",
    "PHASE_SEASON",
    "PHASE_TEAM",
    "TEAMS_PER_SEASON",
    "CurrentSeasonPlanningError",
    "PlannedPage",
    "latest_schedule",
    "linked_months",
    "month_calendar",
    "plan_box_scores",
    "plan_month_pages",
    "plan_season_page",
    "plan_team_pages",
    "require_as_of_in_season",
    "season_page_url",
    "team_page_url",
    "validate_schedule_page",
]
