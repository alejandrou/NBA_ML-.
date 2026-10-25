"""The game loader writes the committed fixture box scores into PostgreSQL.

Every constraint of revision `0009_games_and_box_scores` is in force here — the
regular-expression checks SQLite cannot run among them — so this proves the
loader's rows are rows PostgreSQL accepts, a rerun writes nothing, and a
quarantined game leaves no row.

Environment authorization, connection lifetime, revision checking, and the
rollback that leaves the database as it was found all belong to
`tests/integration/conftest.py`.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, time
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, sessionmaker
from typer.testing import CliRunner

import nba_data.cli.main as cli_main
from nba_data.config.settings import get_settings
from nba_data.db.models import Game, Player, PlayerGameTotals, PlayerSeason, TeamGameTotals
from nba_data.db.repositories import CoreRepository
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.game_pilot_manifest import box_score_url, league_schedule_url
from nba_data.scraping.loaders.games import (
    QUARANTINE_MISSING_TEAM_SEASON,
    GameLineage,
    derive_neutral_sites,
    load_game,
)
from nba_data.scraping.offline_games_backfill import (
    DEFAULT_GAMES_PARSER_VERSION,
    run_offline_games_backfill,
)
from nba_data.scraping.parsers.box_score import parse_box_score_page
from nba_data.scraping.parsers.league_schedule import ScheduleGame

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html"

# The schedule rows these fixture games appear on, as the parser returns them.
TOKYO = (
    2000,
    ScheduleGame(
        game_date=date(1999, 11, 5),
        visitor_code="MIN",
        visitor_name="Minnesota Timberwolves",
        home_code="SAC",
        home_name="Sacramento Kings",
        game_id="199911050SAC",
        visitor_points=95,
        home_points=100,
        start_time="7:00p",
        attendance=32623,
        arena="Tokyo Dome",
        notes="at Tokyo, Japan",
    ),
)
BUBBLE = (
    2020,
    ScheduleGame(
        game_date=date(2020, 8, 17),
        visitor_code="UTA",
        visitor_name="Utah Jazz",
        home_code="DEN",
        home_name="Denver Nuggets",
        game_id="202008170DEN",
        visitor_points=125,
        home_points=135,
        overtime_periods=1,
        start_time="1:30p",
        arena="HP Field House",
    ),
)
FIXTURE_GAMES = (TOKYO, BUBBLE)


def _seed(session: Session, season_year: int, codes: tuple[str, ...]) -> None:
    core = CoreRepository(session)
    season = core.get_or_create_season(league="NBA", season_year=season_year)
    for code in codes:
        team = core.get_or_create_team(basketball_reference_team_id=code, current_abbreviation=code)
        core.get_or_create_team_season(team=team, season=season, team_abbreviation=code)


def _load(session: Session, season_year: int, schedule: ScheduleGame):  # type: ignore[no-untyped-def]
    assert schedule.game_id is not None
    path = FIXTURES / f"box_score_{schedule.game_id}_trimmed.html"
    return load_game(
        session,
        schedule,
        parse_box_score_page(path.read_text(encoding="utf-8")),
        GameLineage(
            source_url=box_score_url(schedule.game_id),
            cache_path=str(path),
            parser_version=DEFAULT_GAMES_PARSER_VERSION,
        ),
        season_end_year=season_year,
    )


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def test_the_fixture_games_load_and_a_rerun_writes_nothing(postgres_session: Session) -> None:
    _seed(postgres_session, 2000, ("MIN", "SAC"))
    _seed(postgres_session, 2020, ("UTA", "DEN"))
    postgres_session.commit()

    first = [_load(postgres_session, season, schedule) for season, schedule in FIXTURE_GAMES]
    postgres_session.commit()

    assert [result.status for result in first] == ["loaded", "loaded"]
    games = {
        game.basketball_reference_game_id: game for game in postgres_session.scalars(select(Game))
    }
    tokyo, bubble = games["199911050SAC"], games["202008170DEN"]
    assert (tokyo.game_type, tokyo.status) == ("regular_season", "final")
    assert tokyo.venue == "Tokyo Dome, Tokyo, Japan"
    assert tokyo.attendance == 32623
    assert tokyo.start_time_et == time(19, 0)
    assert bubble.game_type == "playoffs"
    assert bubble.attendance is None  # blank in the bubble, never zero
    assert bubble.start_time_et == time(13, 30)

    points = dict(
        postgres_session.execute(
            select(TeamGameTotals.is_home, TeamGameTotals.pts).where(
                TeamGameTotals.game_id == bubble.id
            )
        ).all()
    )
    assert points == {False: 125, True: 135}
    assert _count(postgres_session, TeamGameTotals) == 4
    # 12 + 12 lines in Tokyo; 12 + 13 lines and 2 + 4 inactive entries in the bubble.
    assert _count(postgres_session, PlayerGameTotals) == 24 + 25 + 6

    cancar = postgres_session.execute(
        select(Player.full_name, PlayerGameTotals.participation, PlayerGameTotals.pts)
        .join(PlayerGameTotals, PlayerGameTotals.player_id == Player.id)
        .where(Player.basketball_reference_player_id == "cancavl01")
    ).one()
    assert tuple(cancar) == ("Vlatko Čančar", "inactive", None)
    assert _count(postgres_session, PlayerSeason) == 0
    assert set(postgres_session.scalars(select(PlayerGameTotals.parser_version).distinct())) == {
        "box-score-parser-v2"
    }

    neutral = derive_neutral_sites(postgres_session, 2020)
    postgres_session.commit()
    assert neutral.updated == 1  # one home game is its team's home city: decided, not neutral

    players = _count(postgres_session, Player)
    rerun = [_load(postgres_session, season, schedule) for season, schedule in FIXTURE_GAMES]
    assert [result.status for result in rerun] == ["unchanged", "unchanged"]
    assert [result.players_created for result in rerun] == [(), ()]
    assert not postgres_session.dirty and not postgres_session.new
    assert _count(postgres_session, Player) == players
    assert derive_neutral_sites(postgres_session, 2020).updated == 0


def test_a_quarantined_game_leaves_no_row(postgres_session: Session) -> None:
    _seed(postgres_session, 2020, ("UTA",))  # Denver's team-season is absent
    postgres_session.commit()

    season, schedule = BUBBLE
    result = _load(postgres_session, season, schedule)
    postgres_session.commit()

    assert result.status == "quarantined"
    assert [issue.code for issue in result.quarantine] == [QUARANTINE_MISSING_TEAM_SEASON]
    assert _count(postgres_session, Game) == 0
    assert _count(postgres_session, TeamGameTotals) == 0
    assert _count(postgres_session, PlayerGameTotals) == 0
    assert _count(postgres_session, Player) == 0


def test_a_corrected_away_team_replaces_obsolete_totals_and_player_lines(
    postgres_session: Session,
) -> None:
    _seed(postgres_session, 2020, ("UTA", "DEN", "MIN"))
    season, schedule = BUBBLE
    assert _load(postgres_session, season, schedule).status == "loaded"
    postgres_session.commit()
    path = FIXTURES / "box_score_202008170DEN_trimmed.html"
    box = parse_box_score_page(path.read_text(encoding="utf-8"))
    assert box.visitor is not None
    box = replace(box, visitor=replace(box.visitor, code="MIN"))
    lineage = GameLineage(box_score_url(schedule.game_id), str(path), DEFAULT_GAMES_PARSER_VERSION)
    corrected_schedule = replace(schedule, visitor_code="MIN")

    result = load_game(
        postgres_session, corrected_schedule, box, lineage, season_end_year=season,
    )
    postgres_session.commit()

    assert result.status == "loaded"
    assert _count(postgres_session, TeamGameTotals) == 2
    assert _count(postgres_session, PlayerGameTotals) == 31
    assert load_game(
        postgres_session, corrected_schedule, box, lineage, season_end_year=season,
    ).status == "unchanged"


def test_cli_loads_a_real_fixture_from_cache_and_reruns_without_writes(
    postgres_session: Session, postgres_connection: Connection,
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed(postgres_session, 2020, ("UTA", "DEN"))
    postgres_session.commit()
    cache = HtmlCache(tmp_path / "cache")
    row = '''<table id="schedule"><tbody><tr>
        <th data-stat="date_game" csk="20200817">Mon, Aug 17, 2020</th>
        <td data-stat="visitor_team_name"><a href="/teams/UTA/2020.html">Utah Jazz</a></td>
        <td data-stat="home_team_name"><a href="/teams/DEN/2020.html">Denver Nuggets</a></td>
        <td data-stat="visitor_pts">125</td><td data-stat="home_pts">135</td>
        <td data-stat="overtimes">OT</td><td data-stat="game_start_time">1:30p</td>
        <td data-stat="box_score_text"><a href="/boxscores/202008170DEN.html">Box Score</a></td>
        </tr></tbody></table>'''
    cache.set(league_schedule_url(2020),
              '<a href="/leagues/NBA_2020_games-august.html">August</a>' + row)
    cache.set(league_schedule_url(2020, "august"), row)
    cache.set(box_score_url("202008170DEN"),
              (FIXTURES / "box_score_202008170DEN_trimmed.html").read_text(encoding="utf-8"))
    monkeypatch.setenv("SCRAPER_CACHE_DIR", str(cache.root_dir))
    monkeypatch.setattr(cli_main, "create_db_engine", lambda settings: postgres_connection.engine)
    monkeypatch.setattr(cli_main, "create_session_factory", lambda engine: sessionmaker(
        bind=postgres_connection, autoflush=False, expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    ))
    # Only the reviewed count is reduced for this one-game fixture archive.
    monkeypatch.setattr(cli_main, "run_offline_games_backfill", lambda session, **kwargs:
        run_offline_games_backfill(session, **kwargs, expected_counts={2020: 1}))
    args = ["backfill", "games", "--season", "2020", "--execute-approved-games-backfill",
            "--require-complete", "--output", str(tmp_path / "reports")]
    get_settings.cache_clear()
    try:
        first = CliRunner().invoke(cli_main.app, args)
        assert first.exit_code == 0, first.output
        path = tmp_path / "reports" / "NBA_2020_games-backfill.json"
        assert json.loads(path.read_text(encoding="utf-8"))["loaded"] == 1
        stamps = list(postgres_session.scalars(select(PlayerGameTotals.updated_at)))
        rerun = CliRunner().invoke(cli_main.app, args)
        assert rerun.exit_code == 0, rerun.output
        data = json.loads(path.read_text(encoding="utf-8"))
        assert (data["loaded"], data["unchanged"], data["neutral_site_updates"]) == (0, 1, 0)
        assert list(postgres_session.scalars(select(PlayerGameTotals.updated_at))) == stamps
    finally:
        get_settings.cache_clear()
