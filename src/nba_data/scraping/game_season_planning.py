"""Offline planning of the Stage 2 per-season game acquisition (F8-004).

Every URL is derived from pages already in the cache, never guessed:

1. `plan_game_schedules` plans the season page from its fixed URL while it is
   not cached; once it is, it plans every month page the season page links.
   Month URLs cannot be constructed: 2019-20 has `-october-2019` and
   `-october-2020` (F8-001 finding 13).
2. `plan_game_box_scores` reads the cached month pages, selects the season's
   regular-season games plus the NBA Cup final, and checks the count against a
   reviewed per-season table before writing the box-score URLs.

Schedule pages never mark playoff games and show the NBA Cup final like any Cup
game (F8-001 findings 2 and 3), so the selection is by date: with a play-in row
in the season, every played row dated before the first play-in game (the Cup
final is played in December and is included); without one, each team's first
82 played rows. The heading of every fetched box score is confirmed by the
loader (F8-005).

A game's season is the season of the schedule page that lists it, never its
date. Pure planning: the cache is read, nothing is fetched or written to it.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.game_pilot_manifest import (
    PAGE_TYPE_BOX_SCORE,
    PAGE_TYPE_LEAGUE_SCHEDULE,
    box_score_url,
    league_schedule_url,
)
from nba_data.scraping.game_season_manifest import (
    MAX_ABSOLUTE_REQUESTS_PER_MINUTE,
    MAX_DEFAULT_REQUESTS_PER_MINUTE,
    STAGE_2_SEASON_END_YEARS,
    STATUS_DRAFT,
    WRITE_TARGET,
    is_schedule_month,
    validate_game_season_manifest,
)
from nba_data.scraping.parsers.league_schedule import (
    ParsedLeagueSchedule,
    ScheduleGame,
    parse_league_schedule_page,
)

REGULAR_SEASON_GAMES_PER_TEAM = 82

EXPECTED_SELECTED_GAMES: Mapping[int, int] = {
    2015: 1230,
    2016: 1230,
    2017: 1230,
    2018: 1230,
    2019: 1230,
    2020: 1059,
    2021: 1080,
    2022: 1230,
    2023: 1230,
    2024: 1231,
    2025: 1231,
    2026: 1231,
}
"""Reviewed per-season count of selected games: regular season plus Cup final.

2019-20 was cut to 1,059 games by the suspension and the bubble, and 2020-21
was scheduled at 72 games a team. From 2023-24 the NBA Cup final is the 1,231st
game: it is played but does not count toward the regular season. A wrong value
is corrected from the cached pages with the evidence on a card, never loosened.
"""

DRAFT_KIND_SEASON_PAGE = "season-page"
DRAFT_KIND_SCHEDULE_MONTHS = "schedule-months"
DRAFT_KIND_BOX_SCORES = "box-scores"
DEFAULT_DRAFT_DIR = Path("reports/game-season")


class GameSeasonPlanningError(ValueError):
    """Raised when a season cannot be planned safely from the cached pages."""


@dataclass(frozen=True)
class GameSeasonPlan:
    kind: str
    manifest: dict[str, object]
    summary: dict[str, object]


@dataclass(frozen=True)
class _ListedGame:
    game: ScheduleGame
    month: str
    position: int


def plan_game_schedules(
    season_end_year: int,
    *,
    cache: HtmlCache,
    planned_at: datetime,
) -> GameSeasonPlan:
    """Plan the season page, or, once it is cached, every month page it links."""

    _require_stage_2_season(season_end_year)
    season_url = league_schedule_url(season_end_year)
    season_html = cache.get(season_url)

    if season_html is None:
        entries = [
            _schedule_entry(
                season_end_year,
                None,
                "Season page: its month links name the month pages to plan next.",
            )
        ]
        summary: dict[str, object] = {
            "season_end_year": season_end_year,
            "season_page_url": season_url,
            "season_page_cached": False,
            "planned_pages": 1,
            "next_step": "acquire this manifest, then plan the schedules again",
        }
        return _plan(
            DRAFT_KIND_SEASON_PAGE,
            season_end_year,
            PAGE_TYPE_LEAGUE_SCHEDULE,
            entries,
            summary,
            planned_at,
        )

    months = _month_links(_parse(season_html, season_url), season_url)
    entries = [
        _schedule_entry(season_end_year, month, f"Month page linked from {season_url}.")
        for month in months
    ]
    summary = {
        "season_end_year": season_end_year,
        "season_page_url": season_url,
        "season_page_cached": True,
        "months": list(months),
        "planned_pages": len(entries),
        "cached_pages": sum(cache.exists(str(entry["url"])) for entry in entries),
        "next_step": "acquire this manifest, then plan the box scores",
    }
    return _plan(
        DRAFT_KIND_SCHEDULE_MONTHS,
        season_end_year,
        PAGE_TYPE_LEAGUE_SCHEDULE,
        entries,
        summary,
        planned_at,
    )


@dataclass(frozen=True)
class SeasonGameSelection:
    """A season's games chosen by the Stage 2 rule from its cached month pages."""

    season_end_year: int
    season_page_url: str
    months: tuple[str, ...]
    listed_rows: int
    played_rows: int
    rule: str
    first_play_in: date | None
    games: tuple[ScheduleGame, ...]
    months_by_game_id: Mapping[str, str]


def select_season_games(
    season_end_year: int,
    *,
    cache: HtmlCache,
    expected_counts: Mapping[int, int] = EXPECTED_SELECTED_GAMES,
) -> SeasonGameSelection:
    """Select the season's regular-season games plus the Cup final, from the cache only.

    Fails closed: an unplanned season, an uncached or unclean page, or a count
    that differs from the reviewed table raises `GameSeasonPlanningError`.
    """

    _require_stage_2_season(season_end_year)
    expected = expected_counts.get(season_end_year)
    if expected is None:
        msg = f"No reviewed game count exists for the {season_end_year} season"
        raise GameSeasonPlanningError(msg)

    season_url = league_schedule_url(season_end_year)
    season_html = cache.get(season_url)
    if season_html is None:
        msg = f"The season page {season_url} is not cached; plan and acquire the schedules first"
        raise GameSeasonPlanningError(msg)
    season_page = _parse(season_html, season_url)
    months = _month_links(season_page, season_url)

    month_pages: dict[str, ParsedLeagueSchedule] = {}
    missing: list[str] = []
    for month in months:
        url = league_schedule_url(season_end_year, month)
        html = cache.get(url)
        if html is None:
            missing.append(url)
        else:
            month_pages[month] = _parse(html, url)
    if missing:
        msg = f"{len(missing)} month page(s) the season page links are not cached: " + ", ".join(
            missing
        )
        raise GameSeasonPlanningError(msg)

    listed = _listed_games(month_pages)
    _require_season_page_covered(season_page, listed, season_url)
    selected, rule, first_play_in = _select(listed)

    if len(selected) != expected:
        msg = (
            f"Selected {len(selected)} games for the {season_end_year} season, but the "
            f"reviewed count is {expected} ({rule})"
        )
        raise GameSeasonPlanningError(msg)

    return SeasonGameSelection(
        season_end_year=season_end_year,
        season_page_url=season_url,
        months=months,
        listed_rows=len(listed),
        played_rows=sum(listed_game.game.played for listed_game in listed),
        rule=rule,
        first_play_in=first_play_in,
        games=tuple(listed_game.game for listed_game in selected),
        months_by_game_id={
            listed_game.game.game_id: listed_game.month
            for listed_game in selected
            if listed_game.game.game_id is not None
        },
    )


def plan_game_box_scores(
    season_end_year: int,
    *,
    cache: HtmlCache,
    planned_at: datetime,
    expected_counts: Mapping[int, int] = EXPECTED_SELECTED_GAMES,
) -> GameSeasonPlan:
    """Select the season's games from its cached month pages and plan their box scores."""

    selection = select_season_games(
        season_end_year, cache=cache, expected_counts=expected_counts
    )
    entries = [_box_score_entry(season_end_year, game, selection) for game in selection.games]
    summary: dict[str, object] = {
        "season_end_year": season_end_year,
        "season_page_url": selection.season_page_url,
        "months": list(selection.months),
        "listed_rows": selection.listed_rows,
        "played_rows": selection.played_rows,
        "unplayed_rows": selection.listed_rows - selection.played_rows,
        "selection_rule": selection.rule,
        "first_play_in_date": (
            selection.first_play_in.isoformat() if selection.first_play_in else None
        ),
        "selected_games": len(selection.games),
        "expected_games": len(selection.games),
        "excluded_played_rows": selection.played_rows - len(selection.games),
        "cached_pages": sum(cache.exists(str(entry["url"])) for entry in entries),
    }
    return _plan(
        DRAFT_KIND_BOX_SCORES,
        season_end_year,
        PAGE_TYPE_BOX_SCORE,
        entries,
        summary,
        planned_at,
    )


def default_draft_path(season_end_year: int, kind: str) -> Path:
    return DEFAULT_DRAFT_DIR / f"NBA_{season_end_year}_{kind}.draft.json"


def write_draft_manifest(manifest: Mapping[str, object], path: Path) -> Path:
    """Write a draft, refusing to replace any file already at `path`."""

    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
            handle.write("\n")
    except FileExistsError as exc:
        msg = f"{path} already exists; move it away or pass another --output"
        raise GameSeasonPlanningError(msg) from exc
    return path


def _require_stage_2_season(season_end_year: int) -> None:
    if season_end_year not in STAGE_2_SEASON_END_YEARS:
        msg = (
            f"{season_end_year} is not a Stage 2 season "
            f"({STAGE_2_SEASON_END_YEARS[0]}-{STAGE_2_SEASON_END_YEARS[-1]})"
        )
        raise GameSeasonPlanningError(msg)


def _parse(html: str, url: str) -> ParsedLeagueSchedule:
    parsed = parse_league_schedule_page(html)
    if parsed.issues:
        codes = sorted({issue.code for issue in parsed.issues})
        msg = f"The cached schedule page {url} does not parse cleanly: {', '.join(codes)}"
        raise GameSeasonPlanningError(msg)
    return parsed


def _month_links(season_page: ParsedLeagueSchedule, season_url: str) -> tuple[str, ...]:
    if not season_page.month_links:
        msg = f"The cached season page {season_url} links no month pages"
        raise GameSeasonPlanningError(msg)
    unknown = [month for month in season_page.month_links if not is_schedule_month(month)]
    if unknown:
        msg = f"The cached season page {season_url} links unknown months: {unknown}"
        raise GameSeasonPlanningError(msg)
    return season_page.month_links


def _listed_games(month_pages: Mapping[str, ParsedLeagueSchedule]) -> list[_ListedGame]:
    listed: list[_ListedGame] = []
    seen: dict[str, str] = {}
    for month, page in month_pages.items():
        for game in page.games:
            if game.game_id is not None:
                if game.game_id in seen:
                    msg = (
                        f"Game {game.game_id} is listed on both the {seen[game.game_id]} "
                        f"and {month} pages"
                    )
                    raise GameSeasonPlanningError(msg)
                seen[game.game_id] = month
            listed.append(_ListedGame(game=game, month=month, position=len(listed)))
    return listed


def _require_season_page_covered(
    season_page: ParsedLeagueSchedule,
    listed: list[_ListedGame],
    season_url: str,
) -> None:
    """The season page repeats its first month; every game it lists must be in a month page."""

    listed_ids = {listed_game.game.game_id for listed_game in listed}
    uncovered = [
        game.game_id
        for game in season_page.games
        if game.game_id is not None and game.game_id not in listed_ids
    ]
    if uncovered:
        msg = f"{season_url} lists games no month page lists: {uncovered[:5]}"
        raise GameSeasonPlanningError(msg)


def _select(listed: list[_ListedGame]) -> tuple[list[_ListedGame], str, date | None]:
    played = sorted(
        (listed_game for listed_game in listed if listed_game.game.played),
        key=lambda listed_game: (listed_game.game.game_date, listed_game.position),
    )
    play_in_dates = [
        listed_game.game.game_date for listed_game in listed if listed_game.game.play_in
    ]

    if play_in_dates:
        first_play_in = min(play_in_dates)
        selected = [
            listed_game for listed_game in played if listed_game.game.game_date < first_play_in
        ]
        rule = f"played rows dated before the first play-in game ({first_play_in.isoformat()})"
        return selected, rule, first_play_in

    games_played: Counter[str] = Counter()
    selected = []
    for listed_game in played:
        game = listed_game.game
        games_played[game.visitor_code] += 1
        games_played[game.home_code] += 1
        visitor_in = games_played[game.visitor_code] <= REGULAR_SEASON_GAMES_PER_TEAM
        home_in = games_played[game.home_code] <= REGULAR_SEASON_GAMES_PER_TEAM
        if visitor_in and home_in:
            selected.append(listed_game)
        elif visitor_in or home_in:
            msg = (
                f"Game {game.game_id} is within the first {REGULAR_SEASON_GAMES_PER_TEAM} "
                "played rows of one team but not the other"
            )
            raise GameSeasonPlanningError(msg)
    rule = f"each team's first {REGULAR_SEASON_GAMES_PER_TEAM} played rows (no play-in game listed)"
    return selected, rule, None


def _schedule_entry(season_end_year: int, month: str | None, reason: str) -> dict[str, object]:
    return {
        "page_type": PAGE_TYPE_LEAGUE_SCHEDULE,
        "url": league_schedule_url(season_end_year, month),
        "season_end_year": season_end_year,
        "month": month,
        "reason": reason,
    }


def _box_score_entry(
    season_end_year: int,
    game: ScheduleGame,
    selection: SeasonGameSelection,
) -> dict[str, object]:
    if game.game_id is None:  # `played` guarantees an id; this keeps mypy honest
        msg = "A selected game has no box score id"
        raise GameSeasonPlanningError(msg)
    reason = f"{game.game_date.isoformat()} {game.visitor_code} at {game.home_code}"
    if game.notes:
        reason = f"{reason}; {game.notes}"
    month = selection.months_by_game_id[game.game_id]
    return {
        "page_type": PAGE_TYPE_BOX_SCORE,
        "url": box_score_url(game.game_id),
        "season_end_year": season_end_year,
        "game_id": game.game_id,
        "reason": f"{reason} (listed on the {month} page)",
    }


def _plan(
    kind: str,
    season_end_year: int,
    page_type: str,
    entries: list[dict[str, object]],
    summary: dict[str, object],
    planned_at: datetime,
) -> GameSeasonPlan:
    manifest: dict[str, object] = {
        "manifest_id": f"F8-004-NBA_{season_end_year}-{kind}-draft-{planned_at:%Y%m%d}",
        "status": STATUS_DRAFT,
        "approved_by_owner": False,
        "approved_at": None,
        "approval_basis": None,
        "scope": {
            "season_end_year": season_end_year,
            "page_type": page_type,
            "max_urls": len(entries),
        },
        "acquisition_policy": {
            "cache_first": True,
            "sequential": True,
            "stop_on_first_failure": True,
            "requests_per_minute": MAX_DEFAULT_REQUESTS_PER_MINUTE,
            "max_requests_per_minute": MAX_ABSOLUTE_REQUESTS_PER_MINUTE,
            "write_target": WRITE_TARGET,
        },
        "planning": {"planned_at": planned_at.isoformat(), **summary},
        "entries": entries,
    }
    # The draft must load as a draft: the planner never writes what the contract refuses.
    validate_game_season_manifest(manifest, require_approval=False)
    return GameSeasonPlan(kind=kind, manifest=manifest, summary=summary)


__all__ = [
    "DRAFT_KIND_BOX_SCORES",
    "DRAFT_KIND_SCHEDULE_MONTHS",
    "DRAFT_KIND_SEASON_PAGE",
    "EXPECTED_SELECTED_GAMES",
    "GameSeasonPlan",
    "GameSeasonPlanningError",
    "SeasonGameSelection",
    "default_draft_path",
    "plan_game_box_scores",
    "plan_game_schedules",
    "select_season_games",
    "write_draft_manifest",
]
