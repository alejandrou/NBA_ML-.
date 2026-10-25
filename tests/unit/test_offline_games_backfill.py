"""`backfill games`: cache-only selection, one transaction per game, and the season report.

Schedule pages are real-shaped HTML in a temporary cache; each cached box score
holds only its game id, and `parse_box_score_page` is replaced by a builder, so
the gates are exercised by `test_game_loader.py` and these tests stay about
orchestration.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import date
from functools import partial
from pathlib import Path

import pytest
import typer.rich_utils as typer_rich_utils
from click import unstyle
from rich.console import Console
from sqlalchemy import CheckConstraint, MetaData, create_engine, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

import nba_data.cli.main as cli_main
import nba_data.scraping.offline_games_backfill as backfill_module
from nba_data.cli.main import app
from nba_data.config.settings import get_settings
from nba_data.db.models import (
    Game,
    Player,
    PlayerGameTotals,
    PlayerSeason,
    Season,
    Team,
    TeamGameTotals,
    TeamSeason,
)
from nba_data.db.repositories import CoreRepository
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.game_pilot_manifest import box_score_url, league_schedule_url
from nba_data.scraping.offline_games_backfill import (
    DEFAULT_GAMES_PARSER_VERSION,
    run_offline_games_backfill,
)
from nba_data.scraping.parsers.box_score import (
    COUNTING_STATS,
    GAME_TYPE_PLAYOFFS,
    GAME_TYPE_REGULAR_SEASON,
    GAME_TYPE_UNKNOWN,
    PARTICIPATION_PLAYED,
    BoxScorePlayerLine,
    BoxScoreTeam,
    InactivePlayer,
    ParsedBoxScore,
)

SEASON = 2024
TABLES = (Season, Team, Player, PlayerSeason, TeamSeason, Game, TeamGameTotals, PlayerGameTotals)
CODES = ("LAL", "DEN", "BOS", "NYK", "MIA", "PHI")


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


ROWS = {
    "october": [
        Row(date(2023, 10, 24), "LAL", "DEN"),
        Row(date(2023, 10, 25), "BOS", "NYK"),
        Row(date(2023, 10, 26), "MIA", "PHI"),
        Row(date(2023, 10, 27), "BOS", "DEN"),
    ],
    "april": [
        Row(date(2024, 4, 14), "NYK", "DEN"),
        Row(date(2024, 4, 16), "MIA", "PHI", notes="Play-In Game"),
        Row(date(2024, 4, 20), "PHI", "NYK"),
    ],
}
SELECTED = ["202310240DEN", "202310250NYK", "202310260PHI", "202310270DEN", "202404140DEN"]
EXPECTED = {SEASON: len(SELECTED)}


def _row_html(row: Row) -> str:
    date_text = row.game_date.strftime("%a, %b %d, %Y").replace(" 0", " ")
    box = f'<a href="/boxscores/{row.game_id}.html">Box Score</a>' if row.played else ""
    return (
        f'<tr><th data-stat="date_game" csk="{row.game_id}">{date_text}</th>'
        f'<td data-stat="game_start_time">7:00p</td>'
        f'<td data-stat="visitor_team_name"><a href="/teams/{row.visitor}/{SEASON}.html">'
        f"{row.visitor} Team</a></td>"
        f'<td data-stat="visitor_pts">{"101" if row.played else ""}</td>'
        f'<td data-stat="home_team_name"><a href="/teams/{row.home}/{SEASON}.html">'
        f"{row.home} Team</a></td>"
        f'<td data-stat="home_pts">{"99" if row.played else ""}</td>'
        f'<td data-stat="box_score_text">{box}</td>'
        f'<td data-stat="overtimes"></td><td data-stat="attendance">18000</td>'
        f'<td data-stat="game_duration">2:15</td><td data-stat="arena_name">Arena</td>'
        f'<td data-stat="game_remarks">{row.notes}</td></tr>'
    )


def _schedule_page(rows: list[Row]) -> str:
    links = "".join(
        f'<div><a href="/leagues/NBA_{SEASON}_games-{month}.html">{month}</a></div>'
        for month in ROWS
    )
    body = "".join(_row_html(row) for row in rows)
    return (
        f'<html><body><div class="filter">{links}</div><table id="schedule">'
        f"<tbody>{body}</tbody></table></body></html>"
    )


def _cache_season(cache: HtmlCache, *, box_scores: list[str]) -> None:
    cache.set(league_schedule_url(SEASON), _schedule_page(ROWS["october"]))
    for month, rows in ROWS.items():
        cache.set(league_schedule_url(SEASON, month), _schedule_page(rows))
    for game_id in box_scores:
        cache.set(box_score_url(game_id), game_id)


def _team(code: str, points: int, *, inactive: tuple[InactivePlayer, ...] = ()) -> BoxScoreTeam:
    shares = [points // 5] * 5
    shares[0] += points - sum(shares)
    lines = tuple(
        BoxScorePlayerLine(
            player_id=f"{code.lower()}player{index}",
            name=f"{code} Player {index}",
            starter=True,
            participation=PARTICIPATION_PLAYED,
            seconds_played=2880,
            stats={**dict.fromkeys(COUNTING_STATS, 1), "pts": share},
            plus_minus=0,
        )
        for index, share in enumerate(shares)
    )
    totals: dict[str, int | None] = {**dict.fromkeys(COUNTING_STATS, 5), "pts": points}
    return BoxScoreTeam(
        code=code,
        name=f"{code} Team",
        scorebox_points=points,
        line_score=(points - 75, 25, 25, 25),
        line_score_total=points,
        totals_seconds=14400,
        totals=totals,
        players=lines,
        inactive_players=inactive,
    )


def _venue(home: str) -> str:
    return f"{home} Arena, {home} City, State"


BOX_OVERRIDES: dict[str, dict[str, object]] = {}


def _fake_parse(html: str) -> ParsedBoxScore:
    """The cached 'page' is its game id; build the box score that page would hold."""

    game_id = html
    row = next(row for rows in ROWS.values() for row in rows if row.game_id == game_id)
    box = ParsedBoxScore(
        visitor=_team(row.visitor, 101, inactive=(InactivePlayer("youngpa01", "Patric Young"),)),
        home=_team(row.home, 99),
        period_labels=("1", "2", "3", "4"),
        scorebox_meta=(),
        attendance=18000,
        play_by_play_linked=True,
        issues=(),
        heading=f"{row.visitor} at {row.home} Box Score",
        game_type=GAME_TYPE_REGULAR_SEASON,
        venue=_venue(row.home),
    )
    return replace(box, **BOX_OVERRIDES.get(game_id, {}))  # type: ignore[arg-type]


def _sqlite_engine() -> Engine:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    with engine.begin() as connection:
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
        connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS stats")
        for model in TABLES:
            table = model.__table__.to_metadata(metadata)  # type: ignore[attr-defined]
            # SQLite cannot evaluate PostgreSQL's `~` regular expression checks.
            for constraint in list(table.constraints):
                if isinstance(constraint, CheckConstraint) and "~" in str(constraint.sqltext):
                    table.constraints.discard(constraint)
        metadata.create_all(connection)
    with Session(engine) as session:
        core = CoreRepository(session)
        season = core.get_or_create_season(league="NBA", season_year=SEASON)
        for code in CODES:
            team = core.get_or_create_team(
                basketball_reference_team_id=code, current_abbreviation=code
            )
            core.get_or_create_team_season(team=team, season=season, team_abbreviation=code)
        session.commit()
    return engine


@pytest.fixture(autouse=True)
def _fake_box_scores(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    BOX_OVERRIDES.clear()
    monkeypatch.setattr(backfill_module, "parse_box_score_page", _fake_parse)
    yield
    BOX_OVERRIDES.clear()


@pytest.fixture
def session() -> Iterator[Session]:
    engine = _sqlite_engine()
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as test_session:
        yield test_session
    engine.dispose()


@pytest.fixture
def cache(tmp_path: Path) -> HtmlCache:
    return HtmlCache(tmp_path / "cache")


def _run(session: Session, cache: HtmlCache, seasons: tuple[int, ...] = (SEASON,)):  # type: ignore[no-untyped-def]
    return run_offline_games_backfill(
        session, cache=cache, season_end_years=seasons, expected_counts=EXPECTED
    )


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


@pytest.mark.unit
def test_the_selected_cached_games_load_and_the_report_counts_them(
    session: Session, cache: HtmlCache
) -> None:
    _cache_season(cache, box_scores=SELECTED[:4])

    report = _run(session, cache)

    season = report.seasons[0].to_dict()
    assert season["expected"] == 5
    assert season["loaded"] == 4
    assert season["unchanged"] == 0
    assert season["missing_box_score"] == ["202404140DEN"]
    assert season["quarantined"] == {}
    assert season["game_types"] == {GAME_TYPE_REGULAR_SEASON: 4}
    assert season["players_created"] == sorted(
        {"youngpa01"} | {f"{code.lower()}player{i}" for code in CODES for i in range(5)}
    )
    assert season["parser_version"] == DEFAULT_GAMES_PARSER_VERSION == "box-score-parser-v2"
    assert season["schedule_parser_version"] == "league-schedule-parser-v1"
    assert _count(session, Game) == 4
    assert not report.failed()
    assert report.failed(require_complete=True)
    # Play-in and playoff rows are never selected, so no page for them is wanted.
    assert "202404160PHI" not in season["missing_box_score"]


@pytest.mark.unit
def test_a_rerun_over_the_same_cache_is_unchanged_and_writes_nothing(
    session: Session, cache: HtmlCache
) -> None:
    _cache_season(cache, box_scores=SELECTED)
    _run(session, cache)
    stamps = sorted(row.updated_at for row in session.scalars(select(PlayerGameTotals)))

    rerun = _run(session, cache).seasons[0]

    assert (rerun.loaded, rerun.unchanged) == (0, 5)
    assert rerun.players_created == []
    assert rerun.neutral_site_updates == 0
    assert sorted(row.updated_at for row in session.scalars(select(PlayerGameTotals))) == stamps


@pytest.mark.unit
def test_a_quarantined_game_writes_nothing_and_the_others_load(
    session: Session, cache: HtmlCache
) -> None:
    _cache_season(cache, box_scores=SELECTED)
    BOX_OVERRIDES["202310250NYK"] = {"game_type": GAME_TYPE_UNKNOWN}

    report = _run(session, cache)

    season = report.seasons[0]
    assert season.quarantined == {"unknown_game_type": ["202310250NYK"]}
    assert season.to_dict()["quarantined_games"] == 1
    assert season.loaded == 4
    stored = set(session.scalars(select(Game.basketball_reference_game_id)))
    assert stored == set(SELECTED) - {"202310250NYK"}
    assert report.failed()


@pytest.mark.unit
def test_a_game_that_raises_is_rolled_back_alone(
    session: Session, cache: HtmlCache, monkeypatch: pytest.MonkeyPatch
) -> None:
    _cache_season(cache, box_scores=SELECTED)
    real_load = backfill_module.load_game

    def flaky_load(session: Session, schedule, box, lineage, *, season_end_year):  # type: ignore[no-untyped-def]
        result = real_load(session, schedule, box, lineage, season_end_year=season_end_year)
        if schedule.game_id == "202310260PHI":
            raise RuntimeError("disk full")
        return result

    monkeypatch.setattr(backfill_module, "load_game", flaky_load)

    report = _run(session, cache)

    season = report.seasons[0]
    assert season.failed == {"202310260PHI": "RuntimeError: disk full"}
    assert season.loaded == 4
    assert "202310260PHI" not in set(session.scalars(select(Game.basketball_reference_game_id)))
    assert report.failed()


@pytest.mark.unit
def test_a_playoff_heading_is_loaded_with_its_type_and_listed(
    session: Session, cache: HtmlCache
) -> None:
    _cache_season(cache, box_scores=SELECTED)
    BOX_OVERRIDES["202404140DEN"] = {"game_type": GAME_TYPE_PLAYOFFS}

    season = _run(session, cache).seasons[0].to_dict()

    assert season["unexpected_game_types"] == {GAME_TYPE_PLAYOFFS: ["202404140DEN"]}
    assert season["game_types"] == {GAME_TYPE_PLAYOFFS: 1, GAME_TYPE_REGULAR_SEASON: 4}
    assert season["loaded"] == 5


@pytest.mark.unit
def test_neutral_games_are_listed_after_the_season_loads(
    session: Session, cache: HtmlCache
) -> None:
    _cache_season(cache, box_scores=SELECTED)
    BOX_OVERRIDES["202404140DEN"] = {"venue": "Accor Arena, Paris, France"}

    season = _run(session, cache).seasons[0].to_dict()

    assert season["neutral_games"] == [
        {"game_id": "202404140DEN", "venue": "Accor Arena, Paris, France"}
    ]
    stored = dict(
        session.execute(select(Game.basketball_reference_game_id, Game.neutral_site)).all()
    )
    assert stored["202310240DEN"] is False
    assert stored["202404140DEN"] is True


@pytest.mark.unit
def test_an_uncached_schedule_selects_no_game_and_fails(session: Session, cache: HtmlCache) -> None:
    report = _run(session, cache)

    season = report.seasons[0].to_dict()
    assert season["expected"] == 0
    assert "not cached" in str(season["selection_error"])
    assert season["problems"]
    assert report.failed()


@pytest.mark.unit
def test_no_season_requested_fails(session: Session, cache: HtmlCache) -> None:
    assert _run(session, cache, seasons=()).failed()


@pytest.mark.unit
def test_the_backfill_never_reaches_for_an_http_client() -> None:
    source = Path(backfill_module.__file__).read_text(encoding="utf-8")

    assert "client" not in source.lower().replace("no http client", "")
    assert not hasattr(backfill_module, "BasketballReferenceClient")


@pytest.mark.unit
def test_cli_writes_one_report_per_season_and_exits_nonzero_on_a_quarantine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "cache"
    _cache_season(HtmlCache(cache_dir), box_scores=SELECTED)
    BOX_OVERRIDES["202310250NYK"] = {"home": _team("NYK", 101)}  # the schedule says 99
    engine = _sqlite_engine()

    def no_client(*args: object, **kwargs: object) -> None:
        raise AssertionError("backfill games must not construct an HTTP client")

    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(cli_main, "BasketballReferenceClient", no_client)
    monkeypatch.setattr(cli_main, "create_db_engine", lambda settings: engine)
    monkeypatch.setattr(
        cli_main,
        "run_offline_games_backfill",
        lambda session, **kwargs: run_offline_games_backfill(
            session, **kwargs, expected_counts=EXPECTED
        ),
    )
    get_settings.cache_clear()
    try:
        result = CliRunner().invoke(
            app,
            ["backfill", "games", "--execute-approved-games-backfill", "--season", str(SEASON),
             "--output", str(tmp_path / "reports")],
        )
    finally:
        get_settings.cache_clear()

    assert result.exit_code == 1, result.output
    written = json.loads(
        (tmp_path / "reports" / f"NBA_{SEASON}_games-backfill.json").read_text(encoding="utf-8")
    )
    assert written["quarantined"] == {"score_mismatch": ["202310250NYK"]}
    assert written["loaded"] == 4
    summary = json.loads(result.output)
    assert summary["quarantined_games"] == 1
    assert len(summary["report_paths"]) == 1


@pytest.mark.unit
def test_cli_require_complete_fails_on_a_missing_box_score(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "cache"
    _cache_season(HtmlCache(cache_dir), box_scores=SELECTED[:4])

    def invoke(*flags: str) -> int:
        engine = _sqlite_engine()
        monkeypatch.setattr(cli_main, "create_db_engine", lambda settings: engine)
        result = CliRunner().invoke(app, [
            "backfill", "games", "--execute-approved-games-backfill",
            "--season", str(SEASON), *flags,
        ])
        return result.exit_code

    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(
        cli_main,
        "run_offline_games_backfill",
        lambda session, **kwargs: run_offline_games_backfill(
            session, **kwargs, expected_counts=EXPECTED
        ),
    )
    get_settings.cache_clear()
    try:
        assert invoke() == 0
        assert invoke("--require-complete") == 1
    finally:
        get_settings.cache_clear()


@pytest.mark.unit
@pytest.mark.parametrize("colored", [False, True], ids=["plain", "ansi"])
def test_cli_refuses_writes_before_constructing_an_engine(
    monkeypatch: pytest.MonkeyPatch, colored: bool,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("must refuse before database access")

    monkeypatch.setattr(cli_main, "create_db_engine", forbidden)
    # Exercise CI's ANSI rendering on Windows too, at a deterministic width.
    monkeypatch.setattr(typer_rich_utils, "Console", partial(Console, legacy_windows=False))
    monkeypatch.setattr(typer_rich_utils, "FORCE_TERMINAL", colored)
    monkeypatch.setattr(typer_rich_utils, "COLOR_SYSTEM", "standard" if colored else None)
    monkeypatch.setattr(typer_rich_utils, "MAX_WIDTH", 80)
    result = CliRunner().invoke(app, ["backfill", "games", "--season", str(SEASON)], color=True)
    assert result.exit_code == 2
    if colored:
        assert "\x1b[" in result.output
    assert "--execute-approved-games-backfill" in unstyle(result.output)


@pytest.mark.unit
@pytest.mark.parametrize("page", ["box", "season", "month"])
@pytest.mark.parametrize(
    "payload",
    [b"broken gzip", bytes.fromhex("1f8b08000000000002ff07")],
    ids=["invalid-header", "invalid-deflate"],
)
def test_corrupt_cache_is_reported_without_aborting_the_run(
    session: Session, cache: HtmlCache, page: str, payload: bytes,
) -> None:
    _cache_season(cache, box_scores=SELECTED)
    url = {
        "box": box_score_url(SELECTED[0]),
        "season": league_schedule_url(SEASON),
        "month": league_schedule_url(SEASON, "october"),
    }[page]
    cache.path_for_url(url).write_bytes(payload)

    report = _run(session, cache)

    assert report.failed()
    season = report.seasons[0]
    if page == "box":
        assert season.loaded == 4
        assert SELECTED[0] in season.failed
    else:
        assert season.selection_error
        assert _count(session, Game) == 0


@pytest.mark.unit
def test_partial_season_defers_neutral_inference(session: Session, cache: HtmlCache) -> None:
    _cache_season(cache, box_scores=SELECTED[:1])
    BOX_OVERRIDES[SELECTED[0]] = {"venue": "Accor Arena, Paris, France"}

    report = _run(session, cache).seasons[0]

    assert report.neutral_site_updates == 0
    assert report.warnings["neutral_site"][0]["code"] == "neutral_site_deferred"
    assert session.scalar(select(Game)).neutral_site is None
