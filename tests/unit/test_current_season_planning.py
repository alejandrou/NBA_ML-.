from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from nba_data.scraping.cache import CacheFetchMetadata, HtmlCache
from nba_data.scraping.current_season_manifest import (
    CurrentSeasonManifest,
    build_draft_current_season_manifest,
    validate_current_season_manifest,
)
from nba_data.scraping.current_season_planning import (
    CurrentSeasonPlanningError,
    month_calendar,
    plan_box_scores,
    plan_month_pages,
    plan_team_pages,
    require_as_of_in_season,
)
from nba_data.scraping.snapshot_cache import SnapshotCache

BASE = "https://www.basketball-reference.com"
SEASON_URL = f"{BASE}/leagues/NBA_2027_games.html"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html"
SEASON_PAGE = (FIXTURES / "league_schedule_2027_trimmed.html").read_text(encoding="utf-8")
TEAMS = [
    "ATL",
    "BOS",
    "BRK",
    "CHO",
    "CHI",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GSW",
    "HOU",
    "IND",
    "LAC",
    "LAL",
    "MEM",
    "MIA",
    "MIL",
    "MIN",
    "NOP",
    "NYK",
    "OKC",
    "ORL",
    "PHI",
    "PHO",
    "POR",
    "SAC",
    "SAS",
    "TOR",
    "UTA",
    "WAS",
]
MONTHS = ("october", "november", "december", "january", "february", "march", "april")

Game = tuple[date, str, str, tuple[int, int] | None]


def month_url(month: str) -> str:
    return f"{BASE}/leagues/NBA_2027_games-{month}.html"


def schedule_page(games: Sequence[Game]) -> str:
    """The cached 2027 season page with its rows replaced, in the page's own row markup."""

    head, _, rest = SEASON_PAGE.partition("<tbody>")
    _, _, tail = rest.partition("</tbody>")
    return f"{head}<tbody>{''.join(_row(game) for game in games)}</tbody>{tail}"


def _row(game: Game) -> str:
    day, visitor, home, score = game
    game_id = f"{day:%Y%m%d}0{home}"
    visitor_pts, home_pts = ("", "") if score is None else (str(score[0]), str(score[1]))
    box = "" if score is None else f'<a href="/boxscores/{game_id}.html">Box Score</a>'
    return (
        f'<tr><th class="left" csk="{game_id}" data-stat="date_game" scope="row">'
        f'<a href="/boxscores/index.fcgi?month={day.month}&amp;day={day.day}&amp;year={day.year}">'
        f"{day:%a, %b} {day.day}, {day.year}</a></th>"
        '<td class="right" data-stat="game_start_time">7:00p</td>'
        f'<td class="left" data-stat="visitor_team_name"><a href="/teams/{visitor}/2027.html">'
        f"{visitor} team</a></td>"
        f'<td class="right" data-stat="visitor_pts">{visitor_pts}</td>'
        f'<td class="left" data-stat="home_team_name"><a href="/teams/{home}/2027.html">'
        f"{home} team</a></td>"
        f'<td class="right" data-stat="home_pts">{home_pts}</td>'
        f'<td class="center" data-stat="box_score_text">{box}</td>'
        '<td class="center iz" data-stat="overtimes"></td>'
        '<td class="right" data-stat="attendance"></td>'
        '<td class="right" data-stat="game_duration"></td>'
        '<td class="left" data-stat="arena_name">Arena</td>'
        '<td class="left iz" data-stat="game_remarks"></td></tr>'
    )


def round_of_games(day: date, *, scored: bool, teams: Sequence[str] = TEAMS) -> list[Game]:
    return [
        (day, teams[i], teams[i + 1], (100, 101) if scored else None)
        for i in range(0, len(teams), 2)
    ]


class Snapshots:
    """Writes snapshots with strictly increasing fetch times."""

    def __init__(self, root: Path) -> None:
        self.cache = SnapshotCache(root)
        self.fetched_at = datetime(2026, 10, 1, tzinfo=UTC)

    def put(self, url: str, html: str) -> None:
        self.fetched_at += timedelta(seconds=7)
        self.cache.write(
            url,
            html,
            CacheFetchMetadata(fetched_at=self.fetched_at, http_status=200, final_url=url),
        )


def _manifest(**scope: Any) -> CurrentSeasonManifest:
    raw = build_draft_current_season_manifest(datetime(2026, 11, 7, tzinfo=UTC))
    raw["scope"].update(scope)  # type: ignore[union-attr]
    return validate_current_season_manifest(raw, require_approval=False)


def _seeded(tmp_path: Path, months: dict[str, list[Game]]) -> Snapshots:
    snapshots = Snapshots(tmp_path / "snapshots")
    snapshots.put(SEASON_URL, SEASON_PAGE)
    for month, games in months.items():
        snapshots.put(month_url(month), schedule_page(games))
    return snapshots


def _all_months(**overrides: list[Game]) -> dict[str, list[Game]]:
    months: dict[str, list[Game]] = {month: [] for month in MONTHS}
    months.update(overrides)
    return months


@pytest.mark.unit
def test_month_slugs_map_to_the_calendar_of_their_season() -> None:
    assert month_calendar("october", 2027) == (2026, 10)
    assert month_calendar("december", 2027) == (2026, 12)
    assert month_calendar("january", 2027) == (2027, 1)
    assert month_calendar("october-2020", 2020) == (2020, 10)
    with pytest.raises(CurrentSeasonPlanningError, match="Unknown schedule month"):
        month_calendar("smarch", 2027)


@pytest.mark.unit
def test_as_of_must_fall_in_the_season() -> None:
    require_as_of_in_season(date(2026, 8, 1))
    require_as_of_in_season(date(2027, 10, 31))
    with pytest.raises(CurrentSeasonPlanningError, match="outside the 2027 season"):
        require_as_of_in_season(date(2026, 7, 31))


@pytest.mark.unit
def test_nothing_but_the_season_page_is_planned_before_its_first_snapshot(tmp_path: Path) -> None:
    snapshots = SnapshotCache(tmp_path)
    manifest = _manifest()

    assert plan_month_pages(manifest, snapshots=snapshots, as_of=date(2026, 10, 25)) is None
    assert plan_team_pages(manifest, snapshots=snapshots) is None
    assert plan_box_scores(manifest, snapshots=snapshots, archive=HtmlCache(tmp_path / "a")) == ()


@pytest.mark.unit
def test_every_month_never_fetched_is_planned(tmp_path: Path) -> None:
    snapshots = _seeded(tmp_path, {})

    planned = plan_month_pages(_manifest(), snapshots=snapshots.cache, as_of=date(2026, 10, 25))

    assert planned is not None
    assert [page.month for page in planned] == list(MONTHS)
    assert {page.reason for page in planned} == {"Never fetched."}


@pytest.mark.unit
def test_the_month_of_as_of_and_the_next_are_refetched_and_settled_months_are_not(
    tmp_path: Path,
) -> None:
    october = round_of_games(date(2026, 10, 21), scored=True)
    snapshots = _seeded(tmp_path, _all_months(october=october))

    planned = plan_month_pages(_manifest(), snapshots=snapshots.cache, as_of=date(2026, 11, 20))

    assert planned is not None
    assert [page.month for page in planned] == ["november", "december"]


@pytest.mark.unit
def test_a_month_with_a_late_score_is_refetched(tmp_path: Path) -> None:
    october = round_of_games(date(2026, 10, 21), scored=True) + [
        (date(2026, 10, 30), "BOS", "NYK", None)
    ]
    snapshots = _seeded(tmp_path, _all_months(october=october))

    planned = plan_month_pages(_manifest(), snapshots=snapshots.cache, as_of=date(2026, 12, 15))

    assert planned is not None
    assert [page.month for page in planned] == ["october", "december", "january"]
    assert "2026-10-30 BOS at NYK" in planned[0].reason


@pytest.mark.unit
def test_an_earlier_month_is_refetched_until_its_snapshot_has_no_unscored_past_game(
    tmp_path: Path,
) -> None:
    november = [(date(2026, 11, 30), "BOS", "NYK", None)]
    snapshots = _seeded(tmp_path, _all_months(november=november))

    planned = plan_month_pages(_manifest(), snapshots=snapshots.cache, as_of=date(2027, 1, 5))

    assert planned is not None
    assert [page.month for page in planned] == ["november", "january", "february"]
    snapshots.put(month_url("november"), schedule_page([]))
    planned = plan_month_pages(_manifest(), snapshots=snapshots.cache, as_of=date(2027, 1, 5))
    assert planned is not None
    assert [page.month for page in planned] == ["january", "february"]


@pytest.mark.unit
def test_a_postponed_row_keeps_its_month_refetched_and_never_plans_a_box_score(
    tmp_path: Path,
) -> None:
    postponed = (date(2026, 11, 4), "LAL", "MIA", None)
    november = round_of_games(date(2026, 11, 2), scored=True) + [postponed]
    snapshots = _seeded(tmp_path, _all_months(november=november))
    manifest = _manifest()

    months = plan_month_pages(manifest, snapshots=snapshots.cache, as_of=date(2027, 2, 1))
    box_scores = plan_box_scores(
        manifest, snapshots=snapshots.cache, archive=HtmlCache(tmp_path / "archive")
    )

    assert months is not None
    assert "november" in [page.month for page in months]
    assert len(box_scores) == 15
    assert "202611040MIA" not in {page.game_id for page in box_scores}


@pytest.mark.unit
def test_box_scores_are_scored_games_not_yet_archived(tmp_path: Path) -> None:
    october = round_of_games(date(2026, 10, 21), scored=True) + round_of_games(
        date(2026, 10, 27), scored=False
    )
    snapshots = _seeded(tmp_path, _all_months(october=october))
    archive = HtmlCache(tmp_path / "archive")
    archive.set(f"{BASE}/boxscores/202610210BOS.html", "<html>archived</html>")

    planned = plan_box_scores(_manifest(), snapshots=snapshots.cache, archive=archive)

    assert len(planned) == 14
    assert "202610210BOS" not in {page.game_id for page in planned}
    assert all(page.month == "october" and page.phase == "box_score" for page in planned)


@pytest.mark.unit
def test_box_scores_come_from_the_latest_snapshot_only(tmp_path: Path) -> None:
    snapshots = _seeded(
        tmp_path, _all_months(october=round_of_games(date(2026, 10, 21), scored=False))
    )
    archive = HtmlCache(tmp_path / "archive")
    assert plan_box_scores(_manifest(), snapshots=snapshots.cache, archive=archive) == ()

    snapshots.put(
        month_url("october"), schedule_page(round_of_games(date(2026, 10, 21), scored=True))
    )

    assert len(plan_box_scores(_manifest(), snapshots=snapshots.cache, archive=archive)) == 15


@pytest.mark.unit
def test_team_pages_wait_for_every_month_then_plan_the_30_without_a_snapshot(
    tmp_path: Path,
) -> None:
    october = round_of_games(date(2026, 10, 21), scored=False)
    snapshots = _seeded(tmp_path, {"october": october})
    manifest = _manifest()
    assert plan_team_pages(manifest, snapshots=snapshots.cache) is None

    for month in MONTHS[1:]:
        snapshots.put(month_url(month), schedule_page([]))
    planned = plan_team_pages(manifest, snapshots=snapshots.cache)
    assert planned is not None
    assert [page.team for page in planned] == sorted(TEAMS)
    assert planned[0].url == f"{BASE}/teams/ATL/2027.html"

    snapshots.put(planned[0].url, "<html>team</html>")
    again = plan_team_pages(manifest, snapshots=snapshots.cache)
    assert again is not None
    assert len(again) == 29


@pytest.mark.unit
def test_a_team_count_other_than_30_is_an_error(tmp_path: Path) -> None:
    october = round_of_games(date(2026, 10, 21), scored=False, teams=TEAMS[:28])
    snapshots = _seeded(tmp_path, _all_months(october=october))

    with pytest.raises(CurrentSeasonPlanningError, match="list 28 teams, not 30"):
        plan_team_pages(_manifest(), snapshots=snapshots.cache)


@pytest.mark.unit
def test_a_ceiling_is_never_trimmed(tmp_path: Path) -> None:
    october = round_of_games(date(2026, 10, 21), scored=True)
    snapshots = _seeded(tmp_path, _all_months(october=october))
    archive = HtmlCache(tmp_path / "archive")

    with pytest.raises(CurrentSeasonPlanningError, match="15 box scores, above .* ceiling of 14"):
        plan_box_scores(
            _manifest(max_box_scores_per_run=14), snapshots=snapshots.cache, archive=archive
        )
    with pytest.raises(CurrentSeasonPlanningError, match="30 team pages, above .* ceiling of 29"):
        plan_team_pages(_manifest(max_team_pages_per_run=29), snapshots=snapshots.cache)
    with pytest.raises(CurrentSeasonPlanningError, match="3 schedule pages, above .* ceiling of 2"):
        plan_month_pages(
            _manifest(max_schedule_pages_per_run=2),
            snapshots=snapshots.cache,
            as_of=date(2026, 11, 20),
        )


@pytest.mark.unit
def test_a_snapshot_that_does_not_parse_cleanly_stops_the_plan(tmp_path: Path) -> None:
    snapshots = _seeded(tmp_path, {})
    snapshots.put(month_url("october"), "<html><body>no table</body></html>")

    with pytest.raises(CurrentSeasonPlanningError, match="schedule_table_missing"):
        plan_box_scores(_manifest(), snapshots=snapshots.cache, archive=HtmlCache(tmp_path / "a"))


@pytest.mark.unit
def test_wrong_season_in_an_existing_snapshot_is_refused(tmp_path: Path) -> None:
    snapshots = _seeded(
        tmp_path, _all_months(october=[(date(2025, 10, 21), "BOS", "NYK", (100, 99))])
    )
    with pytest.raises(CurrentSeasonPlanningError, match="outside the current season"):
        plan_box_scores(_manifest(), snapshots=snapshots.cache, archive=HtmlCache(tmp_path / "a"))


@pytest.mark.unit
def test_a_game_listed_on_two_months_stops_the_plan(tmp_path: Path) -> None:
    game = (date(2026, 10, 31), "BOS", "NYK", (100, 99))
    snapshots = _seeded(tmp_path, _all_months(october=[game], november=[game]))

    with pytest.raises(CurrentSeasonPlanningError, match="listed on both"):
        plan_box_scores(_manifest(), snapshots=snapshots.cache, archive=HtmlCache(tmp_path / "a"))
