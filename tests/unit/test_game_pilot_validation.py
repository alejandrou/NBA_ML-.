from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nba_data.cli.main import app
from nba_data.config.settings import get_settings
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.game_pilot_manifest import (
    GamePilotManifest,
    box_score_url,
    league_schedule_url,
    play_by_play_url,
    validate_game_pilot_manifest,
)
from nba_data.validation.game_pilot import (
    CHECK_EXPECTED_GAP,
    CHECK_FAILED,
    CHECK_NOT_CHECKED,
    CHECK_PASSED,
    GamePilotGameResult,
    GamePilotValidationReport,
    build_game_pilot_validation_report,
    known_player_ids_from_cache,
)

STATS = (
    "fg",
    "fga",
    "fg3",
    "fg3a",
    "ft",
    "fta",
    "orb",
    "drb",
    "trb",
    "ast",
    "stl",
    "blk",
    "tov",
    "pf",
)


@dataclass(frozen=True)
class Line:
    player_id: str
    fg: int = 0
    fg3: int = 0
    ft: int = 0
    plus_minus: int = 0
    seconds: int = 48 * 60

    @property
    def pts(self) -> int:
        return 2 * self.fg + self.fg3 + self.ft


@dataclass(frozen=True)
class Game:
    """A regulation game whose schedule, box score, and play-by-play agree."""

    season: int
    date: str
    visitor: str
    home: str
    visitor_lines: tuple[Line, ...]
    home_lines: tuple[Line, ...]
    visitor_periods: tuple[int, ...]
    home_periods: tuple[int, ...]
    scoring: tuple[tuple[int, str, str, int], ...]
    heading_label: str | None = None
    schedule_note: str = ""
    team_turnovers: int = 0
    inactive: tuple[str, ...] = ("injurch01",)
    extra_events: tuple[tuple[int, str, str], ...] = ()

    @property
    def game_id(self) -> str:
        return f"{self.date}0{self.home}"


def _game(season: int = 2024, *, date: str = "20231101") -> Game:
    return Game(
        season=season,
        date=date,
        visitor="BOS",
        home="CHI",
        visitor_lines=(
            Line("tatumja01", fg=1, plus_minus=-1),
            Line("brownja02", fg=1, plus_minus=-1),
            Line("holidjr01", plus_minus=-1),
            Line("porzikr01", plus_minus=-1),
            Line("whitede01", plus_minus=-1),
        ),
        home_lines=(
            Line("lavinza01", fg=1, fg3=1, plus_minus=1),
            Line("derozde01", fg=1, plus_minus=1),
            Line("vucevni01", plus_minus=1),
            Line("whitepa01", plus_minus=1),
            Line("caruso01", plus_minus=1),
        ),
        visitor_periods=(2, 0, 2, 0),
        home_periods=(3, 0, 0, 2),
        scoring=(
            (1, "home", "lavinza01", 3),
            (1, "visitor", "tatumja01", 2),
            (3, "visitor", "brownja02", 2),
            (4, "home", "derozde01", 2),
        ),
    )


def _player_cell(player_id: str) -> str:
    return (
        f'<th data-append-csv="{player_id}" data-stat="player">'
        f'<a href="/players/{player_id[0]}/{player_id}.html">{player_id}</a></th>'
    )


def _box_table(code: str, lines: tuple[Line, ...], bench: str, team_turnovers: int) -> str:
    rows = []
    for line in lines:
        values = {"fg": line.fg, "fga": line.fg, "fg3": line.fg3, "fg3a": line.fg3, "ft": line.ft}
        cells = "".join(f'<td data-stat="{stat}">{values.get(stat, 0)}</td>' for stat in STATS)
        minutes = f"{line.seconds // 60}:{line.seconds % 60:02d}"
        rows.append(
            f'<tr>{_player_cell(line.player_id)}<td data-stat="mp">{minutes}</td>{cells}'
            f'<td data-stat="pts">{line.pts}</td>'
            f'<td data-stat="plus_minus">{line.plus_minus:+d}</td></tr>'
        )
    rows.append('<tr class="thead"><th data-stat="player">Reserves</th></tr>')
    rows.append(
        f'<tr>{_player_cell(bench)}<td data-stat="reason" colspan="20">Did Not Play</td></tr>'
    )
    totals = {
        "fg": sum(line.fg for line in lines),
        "fga": sum(line.fg for line in lines),
        "fg3": sum(line.fg3 for line in lines),
        "fg3a": sum(line.fg3 for line in lines),
        "ft": sum(line.ft for line in lines),
        "fta": sum(line.ft for line in lines),
        "tov": team_turnovers,
    }
    foot = "".join(f'<td data-stat="{stat}">{totals.get(stat, 0)}</td>' for stat in STATS)
    return (
        f'<table id="box-{code}-game-basic"><tbody>{"".join(rows)}</tbody>'
        f'<tfoot><tr><th data-stat="player">Team Totals</th><td data-stat="mp">240</td>{foot}'
        f'<td data-stat="pts">{sum(line.pts for line in lines)}</td></tr></tfoot></table>'
    )


def _box_score_html(game: Game) -> str:
    visitor_points = sum(game.visitor_periods)
    home_points = sum(game.home_periods)
    title = f"{game.visitor} at {game.home} Box Score, some date"
    heading = f"{game.heading_label}: {title}" if game.heading_label else title

    def scorebox(code: str, points: int) -> str:
        return (
            f'<div><strong><a href="/teams/{code}/{game.season}.html">{code} name</a></strong>'
            f'<div class="scores"><div class="score">{points}</div></div></div>'
        )

    def line_row(code: str, periods: tuple[int, ...]) -> str:
        cells = "".join(f"<td>{points}</td>" for points in periods)
        return (
            f'<tr><th><a href="/teams/{code}/{game.season}.html">{code}</a></th>{cells}'
            f"<td>{sum(periods)}</td></tr>"
        )

    inactive = "".join(
        f'<a href="/players/{player[0]}/{player}.html">{player}</a>' for player in game.inactive
    )
    return (
        f"<!doctype html><html><body><h1>{heading}</h1>"
        f'<a href="/boxscores/pbp/{game.game_id}.html">Play-By-Play</a>'
        f'<div class="scorebox">{scorebox(game.visitor, visitor_points)}'
        f"{scorebox(game.home, home_points)}"
        '<div class="scorebox_meta"><div>7:00 PM, November 1, 2023</div><div>United Center, Chicago, Illinois</div></div>'
        "</div>"
        '<div id="all_line_score"><!-- <table id="line_score"><thead><tr><th></th>'
        "<th>1</th><th>2</th><th>3</th><th>4</th><th>T</th></tr></thead><tbody>"
        f"{line_row(game.visitor, game.visitor_periods)}{line_row(game.home, game.home_periods)}"
        "</tbody></table> --></div>"
        f"{_box_table(game.visitor, game.visitor_lines, 'benchbo01', game.team_turnovers)}"
        f"{_box_table(game.home, game.home_lines, 'benchch01', 0)}"
        f"<div><div><strong>Inactive:</strong><span><strong>{game.home}</strong></span>{inactive}"
        "</div><div><strong>Attendance:</strong> 18,000</div></div>"
        "</body></html>"
    )


def _play_by_play_html(game: Game) -> str:
    rows = []
    visitor = home = 0
    for period in range(1, 5):
        rows.append(f'<tr class="thead" id="q{period}"><th colspan="6">Q{period}</th></tr>')
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(period, "th")
        rows.append(
            f'<tr><td>12:00.0</td><td colspan="5">Start of {period}{suffix} quarter</td></tr>'
        )
        for extra_period, side, description in game.extra_events:
            if extra_period == period:
                cells = (
                    f"<td>{description}</td><td></td><td>{visitor}-{home}</td><td></td><td></td>"
                )
                if side == "home":
                    cells = f"<td></td><td></td><td>{visitor}-{home}</td><td></td><td>{description}</td>"
                rows.append(f"<tr><td>8:00.0</td>{cells}</tr>")
        for scored_period, side, player, points in game.scoring:
            if scored_period != period:
                continue
            link = f'<a href="/players/{player[0]}/{player}.html">{player}</a> makes shot'
            if side == "visitor":
                visitor += points
                cells = (
                    f"<td>{link}</td><td>+{points}</td><td>{visitor}-{home}</td><td></td><td></td>"
                )
            else:
                home += points
                cells = (
                    f"<td></td><td></td><td>{visitor}-{home}</td><td>+{points}</td><td>{link}</td>"
                )
            rows.append(f"<tr><td>6:00.0</td>{cells}</tr>")
        rows.append(f'<tr><td>0:00.0</td><td colspan="5">End of {period}{suffix} quarter</td></tr>')
    return f'<!doctype html><html><body><table id="pbp">{"".join(rows)}</table></body></html>'


def _schedule_html(game: Game) -> str:
    played_on = datetime.strptime(game.date, "%Y%m%d").date()
    label = f"{played_on:%a}, {played_on:%b} {played_on.day}, {played_on.year}"
    return (
        '<!doctype html><html><body><table id="schedule"><tbody><tr>'
        f'<th data-stat="date_game">{label}</th>'
        f'<td data-stat="visitor_team_name"><a href="/teams/{game.visitor}/{game.season}.html">V</a></td>'
        f'<td data-stat="visitor_pts">{sum(game.visitor_periods)}</td>'
        f'<td data-stat="home_team_name"><a href="/teams/{game.home}/{game.season}.html">H</a></td>'
        f'<td data-stat="home_pts">{sum(game.home_periods)}</td>'
        f'<td data-stat="box_score_text"><a href="/boxscores/{game.game_id}.html">Box Score</a></td>'
        '<td data-stat="overtimes"></td><td data-stat="attendance">18,000</td>'
        f'<td data-stat="arena_name">United Center</td><td data-stat="game_remarks">{game.schedule_note}</td>'
        "</tr></tbody></table></body></html>"
    )


def _manifest_entries(game: Game, *, with_play_by_play: bool = True) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = [
        {
            "page_type": "league_schedule",
            "url": league_schedule_url(game.season),
            "season_end_year": game.season,
            "reason": "Schedule.",
        },
        {
            "page_type": "box_score",
            "url": box_score_url(game.game_id),
            "season_end_year": game.season,
            "game_id": game.game_id,
            "reason": "Test game.",
        },
    ]
    if with_play_by_play:
        entries.append(
            {
                "page_type": "play_by_play",
                "url": play_by_play_url(game.game_id),
                "season_end_year": game.season,
                "game_id": game.game_id,
                "reason": "Test game.",
            }
        )
    return entries


def _raw_manifest(entries: list[dict[str, object]]) -> dict[str, object]:
    return {
        "manifest_id": "f8-001-validation-test",
        "status": "approved",
        "approved_by_owner": True,
        "approved_at": "2026-09-23T00:00:00Z",
        "approval_basis": "Test.",
        "scope": {"page_types": ["league_schedule", "box_score", "play_by_play"], "max_urls": 3},
        "acquisition_policy": {
            "cache_first": True,
            "sequential": True,
            "stop_on_first_failure": True,
            "requests_per_minute": 10,
            "max_requests_per_minute": 20,
            "write_target": "HtmlCache .html.gz",
        },
        "entries": entries,
    }


def _manifest(game: Game, *, with_play_by_play: bool = True) -> GamePilotManifest:
    return validate_game_pilot_manifest(
        _raw_manifest(_manifest_entries(game, with_play_by_play=with_play_by_play))
    )


def _cache(
    tmp_path: Path,
    game: Game,
    *,
    box_html: str | None = None,
    pbp_html: str | None = None,
    schedule_html: str | None = None,
) -> HtmlCache:
    cache = HtmlCache(tmp_path / "cache")
    cache.set(league_schedule_url(game.season), schedule_html or _schedule_html(game))
    cache.set(box_score_url(game.game_id), box_html or _box_score_html(game))
    cache.set(play_by_play_url(game.game_id), pbp_html or _play_by_play_html(game))
    return cache


def _known_players(game: Game) -> frozenset[str]:
    lines = (*game.visitor_lines, *game.home_lines)
    return frozenset(
        {line.player_id for line in lines} | {"benchbo01", "benchch01"} | set(game.inactive)
    )


def _report(
    game: Game,
    cache: HtmlCache,
    *manifests: GamePilotManifest,
    known_players: frozenset[str] | None = None,
    reports: tuple[dict[str, object], ...] = (),
) -> GamePilotValidationReport:
    return build_game_pilot_validation_report(
        manifests,
        cache=cache,
        known_player_ids=_known_players(game) if known_players is None else known_players,
        known_team_seasons=frozenset({("BOS", 2024), ("CHI", 2024)}),
        archive_last_season=2025,
        acquisition_reports=reports,
    )


def _only_game(
    game: Game,
    cache: HtmlCache,
    *,
    manifest: GamePilotManifest | None = None,
    known_players: frozenset[str] | None = None,
    reports: tuple[dict[str, object], ...] = (),
) -> GamePilotGameResult:
    report = _report(
        game, cache, manifest or _manifest(game), known_players=known_players, reports=reports
    )
    (result,) = report.games
    return result


def _statuses(result: GamePilotGameResult) -> dict[str, str]:
    return {check.code: check.status for check in result.checks}


def _detail(result: GamePilotGameResult, code: str) -> str | None:
    return next(check.detail for check in result.checks if check.code == code)


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()


@pytest.mark.unit
def test_a_consistent_game_passes_every_check(tmp_path: Path) -> None:
    game = _game()

    result = _only_game(game, _cache(tmp_path, game))

    assert result.passed, [check for check in result.checks if check.status == CHECK_FAILED]
    assert set(_statuses(result).values()) == {CHECK_PASSED}
    assert (result.visitor_points, result.home_points) == (4, 5)
    assert result.periods == 4
    assert result.game_type == "regular_season"
    assert result.venue == "United Center, Chicago, Illinois"
    assert result.play_by_play_status == "parsed"
    assert result.participation == {"did_not_play": 2, "played": 10}
    assert result.inactive_players == 1
    assert result.attendance == 18000


@pytest.mark.unit
def test_a_schedule_score_that_disagrees_fails_the_game(tmp_path: Path) -> None:
    game = _game()
    schedule = _schedule_html(game).replace('data-stat="home_pts">5<', 'data-stat="home_pts">6<')

    result = _only_game(game, _cache(tmp_path, game, schedule_html=schedule))

    assert _statuses(result)["final_score_agrees"] == CHECK_FAILED
    assert result.passed is False


@pytest.mark.unit
def test_a_player_line_that_disagrees_with_totals_and_events_fails(tmp_path: Path) -> None:
    game = _game()
    box = _box_score_html(game).replace(
        '<td data-stat="pts">2</td><td data-stat="plus_minus">-1</td>',
        '<td data-stat="pts">3</td><td data-stat="plus_minus">-1</td>',
        1,
    )

    result = _only_game(game, _cache(tmp_path, game, box_html=box))

    assert _statuses(result)["player_sums_match_totals"] == CHECK_FAILED
    assert _detail(result, "player_sums_match_totals") == "BOS: pts 5 vs 4"
    assert _statuses(result)["play_by_play_player_points"] == CHECK_FAILED


@pytest.mark.unit
def test_team_turnovers_above_the_player_sum_are_team_level_not_a_mismatch(tmp_path: Path) -> None:
    game = replace(_game(), team_turnovers=2)

    result = _only_game(game, _cache(tmp_path, game))

    assert _statuses(result)["player_sums_match_totals"] == CHECK_PASSED
    assert result.team_turnovers == {"BOS": 2, "CHI": 0}


@pytest.mark.unit
def test_a_blank_player_column_is_missing_not_team_turnovers(tmp_path: Path) -> None:
    game = replace(_game(), team_turnovers=12)
    # The visitor's five player rows come first; blank their turnovers.
    box = _box_score_html(game).replace(
        '<td data-stat="tov">0</td>', '<td data-stat="tov"></td>', 5
    )

    result = _only_game(game, _cache(tmp_path, game, box_html=box))

    assert _statuses(result)["player_sums_match_totals"] == CHECK_FAILED
    assert _detail(result, "player_sums_match_totals") == "BOS: tov blank on 5 of 5 played lines"
    assert result.team_turnovers == {"BOS": None, "CHI": 0}


@pytest.mark.unit
def test_a_blank_points_cell_is_missing_not_zero(tmp_path: Path) -> None:
    game = _game()
    box = _box_score_html(game).replace(
        '<td data-stat="pts">2</td><td data-stat="plus_minus">-1</td>',
        '<td data-stat="pts"></td><td data-stat="plus_minus">-1</td>',
        1,
    )

    result = _only_game(game, _cache(tmp_path, game, box_html=box))

    assert _detail(result, "player_sums_match_totals") == "BOS: pts blank on 1 of 5 played lines"
    assert _detail(result, "play_by_play_player_points") == (
        "no points on the box score for tatumja01"
    )


@pytest.mark.unit
def test_line_score_rows_of_different_lengths_fail_instead_of_raising(tmp_path: Path) -> None:
    game = _game()
    box = _box_score_html(game).replace(
        "CHI</a></th><td>3</td><td>0</td>", "CHI</a></th><td>3</td>"
    )

    result = _only_game(game, _cache(tmp_path, game, box_html=box))

    assert _statuses(result)["line_score_periods"] == CHECK_FAILED
    assert _statuses(result)["play_by_play_periods"] == CHECK_FAILED
    assert _detail(result, "play_by_play_period_points") == (
        "no comparable line score (BOS 4 periods, CHI 3)"
    )


_MALFORMED_BOX_SCORES: dict[str, Callable[[str], str]] = {
    "no scorebox": lambda html: html.replace('class="scorebox"', 'class="other"'),
    "no line score": lambda html: re.sub(r'<div id="all_line_score">.*?</div>', "", html),
    "ragged line score": lambda html: html.replace("<td>0</td><td>2</td><td>5</td>", "<td>5</td>"),
    "no home box": lambda html: re.sub(r'<table id="box-CHI-game-basic">.*?</table>', "", html),
    "no team totals": lambda html: re.sub(r"<tfoot>.*?</tfoot>", "", html),
    "every stat cell blank": lambda html: re.sub(
        r'(<td data-stat="[a-z0-9_]+"[^>]*>)[^<]*(</td>)', r"\1\2", html
    ),
}


@pytest.mark.unit
@pytest.mark.parametrize("malformation", sorted(_MALFORMED_BOX_SCORES))
def test_a_malformed_box_score_fails_the_game_and_never_raises(
    tmp_path: Path, malformation: str
) -> None:
    game = _game()
    box = _MALFORMED_BOX_SCORES[malformation](_box_score_html(game))
    assert box != _box_score_html(game)

    result = _only_game(game, _cache(tmp_path, game, box_html=box))

    assert result.passed is False
    json.dumps(result.to_dict())


@pytest.mark.unit
def test_a_report_that_validates_no_game_fails(tmp_path: Path) -> None:
    game = _game()
    schedule_only = validate_game_pilot_manifest(_raw_manifest(_manifest_entries(game)[:1]))

    report = _report(game, _cache(tmp_path, game), schedule_only)

    assert report.games == ()
    assert report.passed is False
    assert report.to_dict()["coverage_problems"] == ["the manifests name no game"]


@pytest.mark.unit
def test_a_page_two_manifests_name_is_validated_once(tmp_path: Path) -> None:
    game = _game()
    manifest = _manifest(game)

    report = _report(game, _cache(tmp_path, game), manifest, manifest)

    assert (len(report.schedule_pages), len(report.games)) == (1, 1)
    assert report.passed is True


@pytest.mark.unit
def test_a_schedule_page_that_lists_no_game_fails_the_report(tmp_path: Path) -> None:
    game = _game()
    empty = '<!doctype html><html><body><table id="schedule"><tbody></tbody></table></body></html>'

    report = _report(game, _cache(tmp_path, game, schedule_html=empty), _manifest(game))

    assert report.schedule_pages[0].issues == ("no_games",)
    assert report.passed is False


@pytest.mark.unit
def test_play_by_play_points_in_the_wrong_period_fail(tmp_path: Path) -> None:
    game = _game()
    moved = replace(game, scoring=((2, "home", "lavinza01", 3), *game.scoring[1:]))

    result = _only_game(game, _cache(tmp_path, game, pbp_html=_play_by_play_html(moved)))

    assert _statuses(result)["play_by_play_period_points"] == CHECK_FAILED
    assert _statuses(result)["play_by_play_final_score"] == CHECK_PASSED


@pytest.mark.unit
def test_minutes_within_per_line_rounding_pass_and_beyond_it_fail(tmp_path: Path) -> None:
    base = _game()
    rounded = replace(
        base,
        visitor_lines=(
            replace(base.visitor_lines[0], seconds=48 * 60 - 2),
            *base.visitor_lines[1:],
        ),
    )
    assert (
        _statuses(_only_game(rounded, _cache(tmp_path / "a", rounded)))["minutes_match_game_length"]
        == CHECK_PASSED
    )

    short = replace(
        base,
        visitor_lines=(replace(base.visitor_lines[0], seconds=47 * 60), *base.visitor_lines[1:]),
    )
    result = _only_game(short, _cache(tmp_path / "b", short))
    assert _statuses(result)["minutes_match_game_length"] == CHECK_FAILED
    assert _detail(result, "minutes_match_game_length") == (
        "BOS: players 14340s, game length 14400s, rounding allows 2.5s"
    )


@pytest.mark.unit
def test_plus_minus_published_as_all_zeros_is_an_expected_gap(tmp_path: Path) -> None:
    base = _game()
    zeroed = replace(
        base,
        visitor_lines=tuple(replace(line, plus_minus=0) for line in base.visitor_lines),
        home_lines=tuple(replace(line, plus_minus=0) for line in base.home_lines),
    )

    result = _only_game(zeroed, _cache(tmp_path, zeroed))

    assert _statuses(result)["plus_minus_balances"] == CHECK_EXPECTED_GAP
    assert result.passed is True


@pytest.mark.unit
def test_a_zero_second_line_may_omit_plus_minus_but_a_played_one_may_not(
    tmp_path: Path,
) -> None:
    base = _game()
    cameo = Line("benchbo02", seconds=0)
    with_cameo = replace(base, visitor_lines=(*base.visitor_lines, cameo))
    box = _box_score_html(with_cameo).replace(
        '<td data-stat="pts">0</td><td data-stat="plus_minus">+0</td></tr><tr class="thead">',
        '<td data-stat="pts">0</td><td data-stat="plus_minus"></td></tr><tr class="thead">',
    )
    assert (
        _statuses(_only_game(with_cameo, _cache(tmp_path / "a", with_cameo, box_html=box)))[
            "plus_minus_balances"
        ]
        == CHECK_PASSED
    )

    missing = _box_score_html(base).replace(
        '<td data-stat="plus_minus">-1</td>', '<td data-stat="plus_minus"></td>', 1
    )
    result = _only_game(base, _cache(tmp_path / "b", base, box_html=missing))
    assert _statuses(result)["plus_minus_balances"] == CHECK_FAILED


@pytest.mark.unit
def test_plus_minus_that_is_not_published_at_all_is_not_checked(tmp_path: Path) -> None:
    base = _game()
    box = _box_score_html(base)
    for value in ("-1", "+1"):
        box = box.replace(
            f'<td data-stat="plus_minus">{value}</td>', '<td data-stat="plus_minus"></td>'
        )

    result = _only_game(base, _cache(tmp_path, base, box_html=box))

    assert _statuses(result)["plus_minus_balances"] == CHECK_NOT_CHECKED
    assert result.passed is True


@pytest.mark.unit
def test_the_heading_classifies_the_game_and_must_agree_with_the_play_in_note(
    tmp_path: Path,
) -> None:
    play_in = replace(_game(), heading_label="Play-In Game", schedule_note="Play-In Game")
    result = _only_game(play_in, _cache(tmp_path / "a", play_in))
    assert result.game_type == "play_in"
    assert _statuses(result)["play_in_marked_consistently"] == CHECK_PASSED

    unmarked = replace(_game(), heading_label="Play-In Game")
    result = _only_game(unmarked, _cache(tmp_path / "b", unmarked))
    assert _statuses(result)["play_in_marked_consistently"] == CHECK_FAILED

    playoff = replace(_game(), heading_label="2024 NBA Eastern Conference First Round Game 1")
    result = _only_game(playoff, _cache(tmp_path / "c", playoff))
    assert (result.game_type, result.game_label) == (
        "playoffs",
        "2024 NBA Eastern Conference First Round Game 1",
    )
    assert _statuses(result)["play_in_marked_consistently"] == CHECK_PASSED


@pytest.mark.unit
def test_an_inactive_player_named_by_an_event_is_listed(tmp_path: Path) -> None:
    game = replace(
        _game(),
        extra_events=(
            (
                2,
                "home",
                'Technical foul by <a href="/players/i/injurch01.html">injurch01</a>',
            ),
        ),
    )

    result = _only_game(game, _cache(tmp_path, game))

    assert _statuses(result)["play_by_play_players_listed"] == CHECK_PASSED


@pytest.mark.unit
def test_unknown_players_with_a_line_fail_inside_the_archive_and_are_gaps_beyond_it(
    tmp_path: Path,
) -> None:
    archived = _game()
    known = _known_players(archived) - {"tatumja01"}
    result = _only_game(archived, _cache(tmp_path / "a", archived), known_players=known)
    assert _statuses(result)["players_resolve"] == CHECK_FAILED
    assert result.unresolved_player_ids == ("tatumja01",)

    recent = _game(2026, date="20251101")
    recent_result = _only_game(recent, _cache(tmp_path / "b", recent), known_players=known)
    assert _statuses(recent_result)["players_resolve"] == CHECK_EXPECTED_GAP
    assert _statuses(recent_result)["team_seasons_resolve"] == CHECK_EXPECTED_GAP
    assert recent_result.passed is True


@pytest.mark.unit
def test_an_unknown_inactive_only_player_is_an_expected_gap_inside_the_archive(
    tmp_path: Path,
) -> None:
    game = _game()
    known = _known_players(game) - {"injurch01"}

    result = _only_game(game, _cache(tmp_path, game), known_players=known)

    assert _statuses(result)["players_resolve"] == CHECK_EXPECTED_GAP
    assert _detail(result, "players_resolve") == (
        "1 of 13 not in core.players (inactive only: injurch01)"
    )


@pytest.mark.unit
def test_the_profile_counts_substitutions_and_carry_over_conflicts(tmp_path: Path) -> None:
    sub = "enters the game for"
    game = replace(
        _game(),
        extra_events=(
            (
                1,
                "visitor",
                f'<a href="/players/b/benchbo01.html">x</a> {sub} '
                '<a href="/players/t/tatumja01.html">y</a>',
            ),
            (
                1,
                "visitor",
                f'<a href="/players/t/tatumja01.html">y</a> {sub} '
                '<a href="/players/b/brownja02.html">z</a>',
            ),
            # Brown left in period 1; a period-2 substitution taking him out again
            # means he came back between periods without a logged event.
            (
                2,
                "visitor",
                f'<a href="/players/h/holidjr01.html">w</a> {sub} '
                '<a href="/players/b/brownja02.html">z</a>',
            ),
        ),
    )

    result = _only_game(game, _cache(tmp_path, game))

    profile = result.play_by_play
    assert profile.substitutions == 3
    assert profile.same_clock_substitution_groups == 1
    assert profile.lineup_carryover_conflicts == 1


@pytest.mark.unit
def test_linked_play_by_play_the_manifests_omit_fails_the_game(tmp_path: Path) -> None:
    game = _game()

    result = _only_game(
        game,
        _cache(tmp_path, game),
        manifest=_manifest(game, with_play_by_play=False),
    )

    assert result.play_by_play_status == "not_in_manifest"
    assert _statuses(result)["play_by_play_requested"] == CHECK_FAILED
    assert _statuses(result)["play_by_play_reconciles"] == CHECK_NOT_CHECKED
    assert result.passed is False


@pytest.mark.unit
def test_play_by_play_the_box_score_does_not_link_is_not_checked(tmp_path: Path) -> None:
    game = _game()
    box = _box_score_html(game).replace(
        f'<a href="/boxscores/pbp/{game.game_id}.html">Play-By-Play</a>', ""
    )

    result = _only_game(
        game,
        _cache(tmp_path, game, box_html=box),
        manifest=_manifest(game, with_play_by_play=False),
    )

    assert result.play_by_play_status == "unavailable"
    assert _statuses(result)["play_by_play_reconciles"] == CHECK_NOT_CHECKED
    assert result.passed is True


@pytest.mark.unit
def test_a_game_whose_box_score_is_not_requested_fails(tmp_path: Path) -> None:
    game = _game()
    schedule, _, play_by_play = _manifest_entries(game)
    manifest = validate_game_pilot_manifest(_raw_manifest([schedule, play_by_play]))

    result = _only_game(game, _cache(tmp_path, game), manifest=manifest)

    assert _statuses(result)["box_score_requested"] == CHECK_FAILED
    assert result.passed is False


@pytest.mark.unit
def test_a_requested_page_missing_from_the_cache_fails(tmp_path: Path) -> None:
    game = _game()
    cache = _cache(tmp_path, game)
    cache.path_for_url(play_by_play_url(game.game_id)).unlink()

    result = _only_game(game, cache)

    assert result.play_by_play_status == "not_cached"
    assert _statuses(result)["play_by_play_cached"] == CHECK_FAILED


@pytest.mark.unit
def test_measurements_join_by_url_and_bytes_come_from_the_cache(tmp_path: Path) -> None:
    game = _game()
    cache = _cache(tmp_path, game)
    acquisition = {
        "entries": [
            {
                "url": box_score_url(game.game_id),
                "status": "fetched",
                "requests": 1,
                "elapsed_seconds": 6.5,
            },
            {
                "url": play_by_play_url(game.game_id),
                "status": "fetched",
                "requests": 2,
                "elapsed_seconds": 7.25,
            },
            {"url": league_schedule_url(game.season), "status": "cache_hit", "requests": 0},
        ]
    }

    result = _only_game(game, cache, reports=(acquisition,))

    assert result.requests == 3
    assert result.elapsed_seconds == 13.75
    assert result.bytes == len(_box_score_html(game).encode()) + len(
        _play_by_play_html(game).encode()
    )
    assert result.compressed_bytes > 0


@pytest.mark.unit
def test_known_player_ids_come_from_cached_player_page_names(tmp_path: Path) -> None:
    cache = HtmlCache(tmp_path)
    cache.set("https://www.basketball-reference.com/players/t/tatumja01.html", "<html></html>")
    cache.set("https://www.basketball-reference.com/teams/BOS/2024.html", "<html></html>")

    assert known_player_ids_from_cache(tmp_path) == frozenset({"tatumja01"})
    assert known_player_ids_from_cache(tmp_path / "missing") == frozenset()


@pytest.mark.unit
def test_cli_reconciles_from_the_cache_and_exits_non_zero_on_failure(tmp_path: Path) -> None:
    game = _game()
    cache = _cache(tmp_path, game)
    for player_id in _known_players(game):
        cache.set(
            f"https://www.basketball-reference.com/players/{player_id[0]}/{player_id}.html",
            "<html></html>",
        )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(_raw_manifest(_manifest_entries(game))), encoding="utf-8")
    output = tmp_path / "reports" / "validation.json"
    args = [
        "validate",
        "game-pilot",
        "--manifest",
        str(manifest_path),
        "--cache-root",
        str(tmp_path / "cache"),
        "--output",
        str(output),
    ]

    passed = CliRunner().invoke(app, args)
    assert passed.exit_code == 0, passed.output
    assert json.loads(output.read_text(encoding="utf-8"))["games_passed"] == 1

    cache.path_for_url(play_by_play_url(game.game_id)).unlink()
    failed = CliRunner().invoke(app, args)
    assert failed.exit_code == 1
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["passed"] is False
    assert written["failed_games"] == [game.game_id]


@pytest.mark.unit
def test_cli_exits_non_zero_when_only_the_schedule_manifest_is_given(tmp_path: Path) -> None:
    game = _game()
    _cache(tmp_path, game)
    manifest_path = tmp_path / "schedules.json"
    manifest_path.write_text(
        json.dumps(_raw_manifest(_manifest_entries(game)[:1])), encoding="utf-8"
    )
    output = tmp_path / "validation.json"

    result = CliRunner().invoke(
        app,
        [
            "validate",
            "game-pilot",
            "--manifest",
            str(manifest_path),
            "--cache-root",
            str(tmp_path / "cache"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    written = json.loads(output.read_text(encoding="utf-8"))
    assert (written["passed"], written["games"]) == (False, 0)
    assert written["coverage_problems"] == ["the manifests name no game"]
