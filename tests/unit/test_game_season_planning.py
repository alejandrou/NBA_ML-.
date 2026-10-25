from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.game_pilot_manifest import box_score_url, league_schedule_url
from nba_data.scraping.game_season_manifest import (
    GameSeasonManifestError,
    validate_game_season_manifest,
)
from nba_data.scraping.game_season_planning import (
    DRAFT_KIND_BOX_SCORES,
    DRAFT_KIND_SCHEDULE_MONTHS,
    DRAFT_KIND_SEASON_PAGE,
    EXPECTED_SELECTED_GAMES,
    GameSeasonPlanningError,
    default_draft_path,
    plan_game_box_scores,
    plan_game_schedules,
    write_draft_manifest,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html"
PLANNED_AT = datetime(2026, 10, 25, 12, 0, tzinfo=UTC)


@dataclass(frozen=True)
class Row:
    game_date: date
    visitor: str
    home: str
    played: bool = True
    notes: str = ""

    @property
    def game_id(self) -> str:
        return f"{self.game_date:%Y%m%d}0{self.home}"


def _row_html(row: Row, season_end_year: int) -> str:
    date_text = row.game_date.strftime("%a, %b %d, %Y").replace(" 0", " ")
    box = f'<a href="/boxscores/{row.game_id}.html">Box Score</a>' if row.played else ""
    visitor_points = "101" if row.played else ""
    home_points = "99" if row.played else ""
    return (
        f'<tr><th data-stat="date_game" csk="{row.game_id}">{date_text}</th>'
        f'<td data-stat="game_start_time">7:00p</td>'
        f'<td data-stat="visitor_team_name"><a href="/teams/{row.visitor}/{season_end_year}.html">'
        f"{row.visitor} Team</a></td>"
        f'<td data-stat="visitor_pts">{visitor_points}</td>'
        f'<td data-stat="home_team_name"><a href="/teams/{row.home}/{season_end_year}.html">'
        f"{row.home} Team</a></td>"
        f'<td data-stat="home_pts">{home_points}</td>'
        f'<td data-stat="box_score_text">{box}</td>'
        f'<td data-stat="overtimes"></td><td data-stat="attendance">18000</td>'
        f'<td data-stat="game_duration">2:15</td><td data-stat="arena_name">Arena</td>'
        f'<td data-stat="game_remarks">{row.notes}</td></tr>'
    )


def _schedule_page(season_end_year: int, months: list[str], rows: list[Row]) -> str:
    """A schedule page in the published shape: month links, then the #schedule table."""

    links = "".join(
        f'<div><a href="/leagues/NBA_{season_end_year}_games-{month}.html">{month}</a></div>'
        for month in months
    )
    body = "".join(_row_html(row, season_end_year) for row in rows)
    return (
        f'<!doctype html><html><body><div class="filter">{links}</div>'
        f'<table id="schedule"><thead><tr><th data-stat="date_game">Date</th></tr></thead>'
        f"<tbody>{body}</tbody></table></body></html>"
    )


def _cache_season(
    cache: HtmlCache,
    season_end_year: int,
    pages: dict[str, list[Row]],
    *,
    skip: tuple[str, ...] = (),
) -> None:
    """Cache the season page (a copy of the first month, as published) and each month page."""

    months = list(pages)
    first = pages[months[0]]
    cache.set(league_schedule_url(season_end_year), _schedule_page(season_end_year, months, first))
    for month, rows in pages.items():
        if month not in skip:
            cache.set(
                league_schedule_url(season_end_year, month),
                _schedule_page(season_end_year, months, rows),
            )


def _play_in_season() -> dict[str, list[Row]]:
    """2023-24 in miniature: a Cup final in December, then play-in and unmarked playoff rows."""

    return {
        "october": [
            Row(date(2023, 10, 24), "LAL", "DEN"),
            Row(date(2023, 10, 25), "BOS", "NYK"),
        ],
        "december": [
            Row(date(2023, 12, 7), "IND", "MIL", notes="In-Season Tournament"),
            Row(date(2023, 12, 9), "IND", "LAL", notes="In-Season Tournament"),
            Row(date(2023, 12, 12), "MIA", "ORL", played=False, notes="Postponed"),
        ],
        "april": [
            Row(date(2024, 4, 14), "ATL", "IND"),
            Row(date(2024, 4, 16), "MIA", "PHI", notes="Play-In Game"),
            Row(date(2024, 4, 17), "SAC", "GSW", notes="Play-In Game"),
            Row(date(2024, 4, 20), "PHI", "NYK"),
        ],
        "may": [
            Row(date(2024, 5, 1), "NYK", "PHI"),
            Row(date(2024, 5, 30), "BOS", "IND", played=False),
        ],
    }


def _game_ids(manifest: dict[str, object]) -> list[str]:
    entries = manifest["entries"]
    assert isinstance(entries, list)
    return [entry["game_id"] for entry in entries]


@pytest.mark.unit
def test_the_reviewed_count_table_covers_the_twelve_stage_2_seasons() -> None:
    assert dict(EXPECTED_SELECTED_GAMES) == {
        **dict.fromkeys(range(2015, 2020), 1230),
        2020: 1059,
        2021: 1080,
        2022: 1230,
        2023: 1230,
        **dict.fromkeys(range(2024, 2027), 1231),
    }
    assert sum(EXPECTED_SELECTED_GAMES.values()) == 14_439 + 3


@pytest.mark.unit
def test_an_uncached_season_page_is_planned_first(tmp_path: Path) -> None:
    plan = plan_game_schedules(2024, cache=HtmlCache(tmp_path), planned_at=PLANNED_AT)

    assert plan.kind == DRAFT_KIND_SEASON_PAGE
    assert [entry["url"] for entry in plan.manifest["entries"]] == [league_schedule_url(2024)]
    assert plan.manifest["status"] == "draft"
    assert plan.manifest["approved_by_owner"] is False
    assert plan.manifest["scope"] == {
        "season_end_year": 2024,
        "page_type": "league_schedule",
        "max_urls": 1,
    }
    assert list(tmp_path.rglob("*")) == []


@pytest.mark.unit
def test_a_cached_season_page_plans_every_month_it_links(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    _cache_season(cache, 2024, _play_in_season(), skip=("december", "april", "may"))

    plan = plan_game_schedules(2024, cache=cache, planned_at=PLANNED_AT)

    assert plan.kind == DRAFT_KIND_SCHEDULE_MONTHS
    assert [entry["month"] for entry in plan.manifest["entries"]] == [
        "october",
        "december",
        "april",
        "may",
    ]
    assert plan.summary["cached_pages"] == 1


@pytest.mark.unit
def test_2019_20_month_urls_come_from_the_page_including_its_two_octobers(
    tmp_path: Path,
) -> None:
    cache = HtmlCache(tmp_path)
    page = (FIXTURES / "league_schedule_2020_july_trimmed.html").read_text(encoding="utf-8")
    cache.set(league_schedule_url(2020), page)

    plan = plan_game_schedules(2020, cache=cache, planned_at=PLANNED_AT)

    urls = [entry["url"] for entry in plan.manifest["entries"]]
    assert urls[0] == league_schedule_url(2020, "october-2019")
    assert urls[-1] == league_schedule_url(2020, "october-2020")
    assert len(urls) == 10


@pytest.mark.unit
def test_a_play_in_season_keeps_rows_before_the_first_play_in_date_with_the_cup_final(
    tmp_path: Path,
) -> None:
    cache = HtmlCache(tmp_path)
    _cache_season(cache, 2024, _play_in_season())

    plan = plan_game_box_scores(2024, cache=cache, planned_at=PLANNED_AT, expected_counts={2024: 5})

    assert plan.kind == DRAFT_KIND_BOX_SCORES
    assert _game_ids(plan.manifest) == [
        "202310240DEN",
        "202310250NYK",
        "202312070MIL",
        "202312090LAL",
        "202404140IND",
    ]
    assert plan.summary["first_play_in_date"] == "2024-04-16"
    assert plan.summary["unplayed_rows"] == 2
    assert plan.summary["excluded_played_rows"] == 4
    first = plan.manifest["entries"][0]
    assert first["url"] == box_score_url("202310240DEN")
    assert first["season_end_year"] == 2024
    assert "LAL at DEN" in first["reason"]


@pytest.mark.unit
def test_2019_20_reads_both_october_pages_and_keeps_the_bubble_seeding_games(
    tmp_path: Path,
) -> None:
    cache = HtmlCache(tmp_path)
    pages = {
        "october-2019": [Row(date(2019, 10, 22), "NOP", "TOR")],
        "march": [Row(date(2020, 3, 11), "DEN", "DAL")],
        "august": [
            Row(date(2020, 8, 14), "POR", "BRK"),
            Row(date(2020, 8, 15), "MEM", "POR", notes="Play-In Game"),
            Row(date(2020, 8, 17), "UTA", "DEN"),
        ],
        "october-2020": [Row(date(2020, 10, 11), "MIA", "LAL")],
    }
    _cache_season(cache, 2020, pages)

    plan = plan_game_box_scores(2020, cache=cache, planned_at=PLANNED_AT, expected_counts={2020: 3})

    assert _game_ids(plan.manifest) == ["201910220TOR", "202003110DAL", "202008140BRK"]
    assert plan.summary["months"] == list(pages)
    assert {entry["season_end_year"] for entry in plan.manifest["entries"]} == {2020}


@pytest.mark.unit
def test_a_season_without_play_in_keeps_each_teams_first_82_played_rows(tmp_path: Path) -> None:
    start = date(2015, 10, 27)
    # Two teams meet 85 times: 82 regular-season games, then 3 unmarked playoff games.
    rows = [
        Row(start + timedelta(days=day), *(("AAA", "BBB") if day % 2 else ("BBB", "AAA")))
        for day in range(85)
    ]
    rows.insert(3, Row(start + timedelta(days=3), "CCC", "DDD", played=False))
    cache = HtmlCache(tmp_path)
    _cache_season(cache, 2016, {"october": rows[:6], "november": rows[6:]})

    plan = plan_game_box_scores(
        2016, cache=cache, planned_at=PLANNED_AT, expected_counts={2016: 82}
    )

    game_ids = _game_ids(plan.manifest)
    assert len(game_ids) == 82
    assert game_ids[-1] == rows[82].game_id  # the 82nd played row; one unplayed row precedes it
    assert plan.summary["first_play_in_date"] is None
    assert plan.summary["excluded_played_rows"] == 3


@pytest.mark.unit
def test_a_game_inside_one_teams_82_and_outside_the_others_fails(tmp_path: Path) -> None:
    start = date(2015, 10, 27)
    rows = [Row(start + timedelta(days=day), "AAA", "BBB") for day in range(83)]
    rows.append(Row(start + timedelta(days=90), "AAA", "CCC"))
    cache = HtmlCache(tmp_path)
    _cache_season(cache, 2016, {"october": rows})

    with pytest.raises(GameSeasonPlanningError, match="one team but not the other"):
        plan_game_box_scores(2016, cache=cache, planned_at=PLANNED_AT, expected_counts={2016: 82})


@pytest.mark.unit
def test_a_count_that_differs_from_the_reviewed_table_fails(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    _cache_season(cache, 2024, _play_in_season())

    with pytest.raises(GameSeasonPlanningError, match="Selected 5 games .* reviewed count is 1231"):
        plan_game_box_scores(2024, cache=cache, planned_at=PLANNED_AT)


@pytest.mark.unit
def test_a_missing_month_page_fails_and_names_it(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    _cache_season(cache, 2024, _play_in_season(), skip=("april",))

    with pytest.raises(GameSeasonPlanningError, match="NBA_2024_games-april.html"):
        plan_game_box_scores(2024, cache=cache, planned_at=PLANNED_AT, expected_counts={2024: 5})


@pytest.mark.unit
def test_box_scores_need_the_cached_season_page(tmp_path: Path) -> None:
    with pytest.raises(GameSeasonPlanningError, match="plan and acquire the schedules first"):
        plan_game_box_scores(2024, cache=HtmlCache(tmp_path), planned_at=PLANNED_AT)


@pytest.mark.unit
def test_a_game_listed_on_two_month_pages_fails(tmp_path: Path) -> None:
    pages = _play_in_season()
    pages["december"].append(pages["october"][0])
    cache = HtmlCache(tmp_path)
    _cache_season(cache, 2024, pages)

    with pytest.raises(GameSeasonPlanningError, match="202310240DEN is listed on both"):
        plan_game_box_scores(2024, cache=cache, planned_at=PLANNED_AT, expected_counts={2024: 5})


@pytest.mark.unit
def test_a_season_page_game_missing_from_every_month_page_fails(tmp_path: Path) -> None:
    pages = _play_in_season()
    cache = HtmlCache(tmp_path)
    _cache_season(cache, 2024, pages)
    extra = [*pages["october"], Row(date(2023, 10, 26), "PHX", "GSW")]
    cache.set(league_schedule_url(2024), _schedule_page(2024, list(pages), extra))

    with pytest.raises(GameSeasonPlanningError, match="lists games no month page lists"):
        plan_game_box_scores(2024, cache=cache, planned_at=PLANNED_AT, expected_counts={2024: 5})


@pytest.mark.unit
def test_a_schedule_page_that_does_not_parse_cleanly_fails(tmp_path: Path) -> None:
    pages = _play_in_season()
    cache = HtmlCache(tmp_path)
    _cache_season(cache, 2024, pages)
    cache.set(league_schedule_url(2024, "may"), "<!doctype html><html><body></body></html>")

    with pytest.raises(GameSeasonPlanningError, match="schedule_table_missing"):
        plan_game_box_scores(2024, cache=cache, planned_at=PLANNED_AT, expected_counts={2024: 5})


@pytest.mark.unit
@pytest.mark.parametrize("season", [2014, 2027])
def test_only_stage_2_seasons_are_planned(tmp_path: Path, season: int) -> None:
    with pytest.raises(GameSeasonPlanningError, match="not a Stage 2 season"):
        plan_game_schedules(season, cache=HtmlCache(tmp_path), planned_at=PLANNED_AT)


@pytest.mark.unit
def test_drafts_load_for_planning_and_are_refused_for_acquisition(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    _cache_season(cache, 2024, _play_in_season())
    plan = plan_game_box_scores(2024, cache=cache, planned_at=PLANNED_AT, expected_counts={2024: 5})

    draft = validate_game_season_manifest(plan.manifest, require_approval=False)
    assert draft.approved is False
    assert len(draft.entries) == 5
    with pytest.raises(GameSeasonManifestError, match="status must be 'approved'"):
        validate_game_season_manifest(plan.manifest, require_approval=True)


@pytest.mark.unit
def test_a_draft_is_written_once_and_never_overwritten(tmp_path: Path) -> None:
    plan = plan_game_schedules(2024, cache=HtmlCache(tmp_path / "cache"), planned_at=PLANNED_AT)
    path = tmp_path / "reports" / "draft.json"

    write_draft_manifest(plan.manifest, path)
    path.write_text('{"edited": true}', encoding="utf-8")
    with pytest.raises(GameSeasonPlanningError, match="already exists"):
        write_draft_manifest(plan.manifest, path)

    assert json.loads(path.read_text(encoding="utf-8")) == {"edited": True}


@pytest.mark.unit
def test_default_drafts_live_under_reports() -> None:
    assert default_draft_path(2024, DRAFT_KIND_BOX_SCORES) == Path(
        "reports/game-season/NBA_2024_box-scores.draft.json"
    )
