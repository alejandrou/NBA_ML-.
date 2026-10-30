"""`load_team_game_history` reads two seasons of PostgreSQL games without writing.

Every constraint of revision `0009_games_and_box_scores` is in force here, so
the seeded games are games the real schema accepts. A cup final is history; a
scheduled game, a postponed one, and a playoff game are not.

Environment authorization, connection lifetime, revision checking, and the
rollback that leaves the database as it was found all belong to
`tests/integration/conftest.py`.
"""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy.orm import Session

from nba_data.db.models import Game, Season, Team, TeamGameTotals, TeamSeason
from nba_data.ml.team_games import TeamBox, TeamGameRecord, load_team_game_history

pytestmark = pytest.mark.integration

_LINEAGE = {
    "source_url": "https://www.basketball-reference.com/boxscores/probe.html",
    "cache_path": "boxscores/probe.html",
    "parser_version": "probe",
}


def _seed(session: Session) -> None:
    seasons = {
        year: Season(season_year=year, league="NBA", label=str(year)) for year in (2024, 2025)
    }
    teams = {
        code: Team(basketball_reference_team_id=code, current_name=code) for code in ("BOS", "NYK")
    }
    session.add_all([*seasons.values(), *teams.values()])
    session.flush()
    team_seasons = {
        (code, year): TeamSeason(team_id=team.id, season_id=season.id, team_abbreviation=code)
        for code, team in teams.items()
        for year, season in seasons.items()
    }
    session.add_all(team_seasons.values())
    session.flush()

    games = [
        ("202403010BOS", 2024, "BOS", "NYK", date(2024, 3, 1), "regular_season", "final", False, (118, 104)),
        ("202404250NYK", 2024, "NYK", "BOS", date(2024, 4, 25), "playoffs", "final", False, (99, 101)),
        ("202312090NYK", 2024, "NYK", "BOS", date(2023, 12, 9), "cup_final", "final", True, (100, 109)),
        ("202411020NYK", 2025, "NYK", "BOS", date(2024, 11, 2), "regular_season", "final", None, (112, 111)),
        ("202411200BOS", 2025, "BOS", "NYK", date(2024, 11, 20), None, "scheduled", None, None),
        ("202411220NYK", 2025, "NYK", "BOS", date(2024, 11, 22), None, "postponed", None, None),
    ]  # fmt: skip
    for game_id, year, home, away, day, game_type, status, neutral, score in games:
        home_ts, away_ts = team_seasons[(home, year)], team_seasons[(away, year)]
        game = Game(
            basketball_reference_game_id=game_id,
            season_id=seasons[year].id,
            home_team_season_id=home_ts.id,
            away_team_season_id=away_ts.id,
            game_date=day,
            start_time_et=time(19, 30),
            game_type=game_type,
            status=status,
            neutral_site=neutral,
        )
        session.add(game)
        session.flush()
        if score is None:
            continue
        for team_season, is_home, pts in ((home_ts, True, score[0]), (away_ts, False, score[1])):
            session.add(
                TeamGameTotals(
                    game_id=game.id,
                    team_season_id=team_season.id,
                    is_home=is_home,
                    seconds_played=14400 if game_id != "202411020NYK" else 15900,
                    pts=pts,
                    fg=42,
                    fga=88,
                    fg3=14,
                    ft=17,
                    fta=21,
                    orb=9,
                    drb=34,
                    trb=43,
                    tov=None if (game_id, is_home) == ("202411020NYK", False) else 12,
                    **_LINEAGE,
                )
            )
    session.flush()


def _box(code: str, pts: int, *, seconds: int = 14400, tov: int | None = 12) -> TeamBox:
    return TeamBox(code, pts, seconds, 42, 88, 14, 17, 21, 9, 34, tov)


def test_two_seasons_of_history_come_back_as_frozen_records(
    postgres_session: Session,
) -> None:
    _seed(postgres_session)

    records = load_team_game_history(postgres_session)

    assert records == [
        TeamGameRecord(
            "202312090NYK", 2024, date(2023, 12, 9), "cup_final", "final", True,
            _box("NYK", 100), _box("BOS", 109),
        ),
        TeamGameRecord(
            "202403010BOS", 2024, date(2024, 3, 1), "regular_season", "final", False,
            _box("BOS", 118), _box("NYK", 104),
        ),
        TeamGameRecord(
            "202411020NYK", 2025, date(2024, 11, 2), "regular_season", "final", None,
            _box("NYK", 112, seconds=15900), _box("BOS", 111, seconds=15900, tov=None),
        ),
    ]  # fmt: skip


def test_the_read_adds_flushes_and_commits_nothing(postgres_session: Session) -> None:
    _seed(postgres_session)
    postgres_session.commit = _refuse  # type: ignore[method-assign]
    postgres_session.flush = _refuse  # type: ignore[method-assign]

    load_team_game_history(postgres_session)

    assert not postgres_session.new
    assert not postgres_session.dirty
    assert not postgres_session.deleted


def test_the_read_leaves_pending_changes_unflushed_with_autoflush_on(
    postgres_session: Session,
) -> None:
    _seed(postgres_session)
    # The fixture turns autoflush off; a caller's Session usually has it on.
    postgres_session.autoflush = True
    team = postgres_session.query(Team).filter_by(basketball_reference_team_id="BOS").one()
    team.current_name = "Renamed"
    postgres_session.flush = _refuse  # type: ignore[method-assign]

    load_team_game_history(postgres_session)

    assert team in postgres_session.dirty


def _refuse(*args: object, **kwargs: object) -> None:
    raise AssertionError("the history read must not flush or commit")
