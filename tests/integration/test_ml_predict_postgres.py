"""`register_model` and `publish_predictions` against real tables and a real artifact."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from nba_data.db.models import (
    Game,
    ModelVersion,
    Prediction,
    Season,
    Team,
    TeamGameTotals,
    TeamSeason,
)
from nba_data.ml.artifact import save_artifact
from nba_data.ml.models import EloModel, HomeRateModel
from nba_data.ml.predict import PredictionError, publish_predictions, round_probabilities
from nba_data.ml.register import ModelRegistrationError, activate_model, register_model
from nba_data.ml.team_features import FEATURE_DEFINITION_VERSION

pytestmark = pytest.mark.integration

OPENING = date(2026, 11, 1)
HOME_RATE = 0.6251234567
WINDOW = {"start": date(2026, 12, 1), "end": date(2026, 12, 31)}


class League:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.season = Season(season_year=2027, league="NBA")
        session.add(self.season)
        session.flush()
        self.teams = {code: self._team_season(code) for code in ("AAA", "BBB", "CCC", "DDD")}

    def _team_season(self, code: str) -> TeamSeason:
        team = Team(basketball_reference_team_id=code, current_name=code)
        self.session.add(team)
        self.session.flush()
        row = TeamSeason(team_id=team.id, season_id=self.season.id, team_abbreviation=code)
        self.session.add(row)
        self.session.flush()
        return row

    def game(
        self,
        played: date,
        home: str,
        away: str,
        status: str = "final",
        *,
        venue: str | None = "",
        blank_box: bool = False,
    ) -> Game:
        if venue == "":
            venue = f"{home} Arena, City" if status == "final" else f"{home} Arena"
        game = Game(
            basketball_reference_game_id=f"{played:%Y%m%d}0{home}",
            season_id=self.season.id,
            home_team_season_id=self.teams[home].id,
            away_team_season_id=self.teams[away].id,
            game_date=played,
            game_type="regular_season" if status == "final" else None,
            status=status,
            neutral_site=None,
            venue=venue,
        )
        self.session.add(game)
        self.session.flush()
        if status == "final":
            self._box(game, home, is_home=True, points=112, blank=blank_box)
            self._box(game, away, is_home=False, points=101, blank=blank_box)
        return game

    def _box(
        self, game: Game, code: str, *, is_home: bool, points: int, blank: bool = False
    ) -> None:
        counters: dict[str, int | None] = {
            "seconds_played": 14_400,
            "pts": points,
            "fg": 40,
            "fga": 85,
            "fg3": 12,
            "fg3a": 33,
            "ft": 15,
            "fta": 20,
            "orb": 10,
            "drb": 32,
            "trb": 42,
            "ast": 25,
            "stl": 7,
            "blk": 5,
            "tov": 13,
            "pf": 19,
        }
        if blank:
            # The table requires these two; every other counter may be blank.
            counters = {**dict.fromkeys(counters), "seconds_played": 14_400, "pts": points}
        self.session.add(
            TeamGameTotals(
                game_id=game.id,
                team_season_id=self.teams[code].id,
                is_home=is_home,
                **counters,
                source_url="https://www.basketball-reference.com/boxscores/x.html",
                cache_path="boxscores/x.html",
                parser_version="probe",
            )
        )
        self.session.flush()

    def history(self, home: str, away: str, count: int, first: int = 0) -> None:
        for offset in range(first, first + count):
            self.game(OPENING + timedelta(days=offset), home, away)


@pytest.fixture
def league(postgres_session: Session) -> League:
    return League(postgres_session)


def _save(tmp_path: Path, model: Any, name: str) -> Path:
    metadata = {
        "model": name,
        "feature_definition_version": FEATURE_DEFINITION_VERSION,
        "training_window": "last_5",
        "training_seasons": [2025, 2026],
        "configuration": {},
        "calibration": {"kept": False},
        "metrics": {"stage_5_go": True},
    }
    return save_artifact(model, metadata, tmp_path).path


@pytest.fixture
def artifact(tmp_path: Path, postgres_session: Session) -> Path:
    model = HomeRateModel()
    model.home_rate = HOME_RATE
    path = _save(tmp_path, model, "home-rate")
    register_model(postgres_session, path, activate=True)
    return path


def _rows(session: Session, game: Game) -> list[Prediction]:
    session.expire_all()
    return list(
        session.scalars(
            select(Prediction)
            .where(Prediction.game_id == game.id)
            .order_by(Prediction.cutoff_date)
        )
    )


def _publish(session: Session, tmp_path: Path) -> Any:
    return publish_predictions(session, artifact_dir=tmp_path, **WINDOW)


def test_the_outcomes_of_one_run(
    league: League, artifact: Path, tmp_path: Path, postgres_session: Session
) -> None:
    league.history("AAA", "BBB", 5)
    league.history("CCC", "DDD", 4)
    ready = league.game(date(2026, 12, 20), "AAA", "BBB", "scheduled")
    short = league.game(date(2026, 12, 20), "CCC", "DDD", "scheduled")
    played = league.game(date(2026, 12, 1), "AAA", "BBB")
    postponed = league.game(date(2026, 12, 21), "BBB", "DDD", "postponed")

    report = _publish(postgres_session, tmp_path)

    home, away, favorite = round_probabilities(HOME_RATE)
    [available] = _rows(postgres_session, ready)
    assert available.status == "available"
    assert available.home_win_probability == home
    assert available.away_win_probability == away
    assert available.home_win_probability + available.away_win_probability == Decimal(1)
    assert available.favorite == favorite
    assert available.availability_included is False
    # The five of `history`, and the final game inside the window.
    assert available.inputs["games_in_season_before_home"] == 6

    assert _rows(postgres_session, short)[0].unavailable_reason == "insufficient_history"
    assert _rows(postgres_session, played)[0].unavailable_reason == "game_not_scheduled"
    assert _rows(postgres_session, postponed)[0].unavailable_reason == "game_not_scheduled"
    assert report.written == 4
    assert report.latest_complete_date == date(2026, 12, 1)


def test_a_finished_game_keeps_its_forecast(
    league: League, artifact: Path, tmp_path: Path, postgres_session: Session
) -> None:
    league.history("AAA", "BBB", 5)
    game = league.game(date(2026, 12, 20), "AAA", "BBB", "scheduled")
    _publish(postgres_session, tmp_path)
    issued = _rows(postgres_session, game)

    game.status = "final"
    game.game_type = "regular_season"
    # A later cutoff is what used to bury the forecast.
    league.game(OPENING + timedelta(days=5), "AAA", "BBB")
    postgres_session.flush()
    report = _publish(postgres_session, tmp_path)

    assert [row.id for row in _rows(postgres_session, game)] == [row.id for row in issued]
    assert issued[0].status == "available"
    assert report.kept_issued == 1


def test_a_postponed_game_keeps_its_rows_and_is_reported(
    league: League, artifact: Path, tmp_path: Path, postgres_session: Session
) -> None:
    league.history("AAA", "BBB", 5)
    game = league.game(date(2026, 12, 20), "AAA", "BBB", "scheduled")
    _publish(postgres_session, tmp_path)
    before = [row.id for row in _rows(postgres_session, game)]

    game.status = "postponed"
    postgres_session.flush()
    report = _publish(postgres_session, tmp_path)

    assert [row.id for row in _rows(postgres_session, game)] == before
    assert report.postponed_with_forecast == [game.basketball_reference_game_id]
    assert report.written == 0


def test_an_unconfirmed_game_is_withheld_and_named(
    league: League, artifact: Path, tmp_path: Path, postgres_session: Session
) -> None:
    league.history("AAA", "BBB", 5)
    league.game(date(2026, 12, 19), "AAA", "BBB", "scheduled")
    away_floor = league.game(date(2026, 12, 20), "AAA", "BBB", "scheduled", venue="Other Arena")
    no_arena = league.game(date(2026, 12, 21), "AAA", "BBB", "scheduled", venue=None)

    report = _publish(postgres_session, tmp_path)

    assert report.withheld == {
        "unconfirmed_competition": [away_floor.basketball_reference_game_id],
        "unknown_venue": [no_arena.basketball_reference_game_id],
    }
    assert _rows(postgres_session, away_floor) == []
    assert _rows(postgres_session, no_arena) == []


def test_blank_box_scores_never_yield_a_forecast(
    league: League, artifact: Path, tmp_path: Path, postgres_session: Session
) -> None:
    for offset in range(5):
        league.game(OPENING + timedelta(days=offset), "AAA", "BBB", blank_box=True)
    game = league.game(date(2026, 12, 20), "AAA", "BBB", "scheduled")

    report = _publish(postgres_session, tmp_path)

    [row] = _rows(postgres_session, game)
    assert row.unavailable_reason == "insufficient_history"
    assert report.blocked_by_blank_statistics == 1


def test_a_replacement_is_prepared_then_activated_without_a_gap(
    league: League, artifact: Path, tmp_path: Path, postgres_session: Session
) -> None:
    league.history("AAA", "BBB", 5)
    game = league.game(date(2026, 12, 20), "AAA", "BBB", "scheduled")
    _publish(postgres_session, tmp_path)
    model = HomeRateModel()
    model.home_rate = 0.7
    replacement = _save(tmp_path, model, "home-rate")

    with pytest.raises(ModelRegistrationError, match="no forecast for 1 scheduled"):
        register_model(postgres_session, replacement, activate=True)
    assert not register_model(postgres_session, replacement).is_active
    publish_predictions(
        postgres_session, artifact_dir=tmp_path, model_name=replacement.name, **WINDOW
    )
    active = postgres_session.scalars(select(ModelVersion.name).where(ModelVersion.is_active)).one()
    assert active == artifact.name

    assert activate_model(postgres_session, replacement.name).is_active
    assert len(_rows(postgres_session, game)) == 2
    with pytest.raises(ModelRegistrationError, match="not registered"):
        activate_model(postgres_session, "nothing")


def test_a_rerun_writes_nothing(
    league: League, artifact: Path, tmp_path: Path, postgres_session: Session
) -> None:
    league.history("AAA", "BBB", 5)
    game = league.game(date(2026, 12, 20), "AAA", "BBB", "scheduled")

    _publish(postgres_session, tmp_path)
    before = _rows(postgres_session, game)[0].id
    report = _publish(postgres_session, tmp_path)

    assert (report.written, report.unchanged) == (0, 1)
    assert [row.id for row in _rows(postgres_session, game)] == [before]


def test_a_later_cutoff_writes_a_new_row_and_keeps_the_old(
    league: League, artifact: Path, tmp_path: Path, postgres_session: Session
) -> None:
    league.history("AAA", "BBB", 5)
    game = league.game(date(2026, 12, 20), "AAA", "BBB", "scheduled")
    _publish(postgres_session, tmp_path)

    league.game(OPENING + timedelta(days=5), "AAA", "BBB")
    report = _publish(postgres_session, tmp_path)

    rows = _rows(postgres_session, game)
    assert report.written == 1
    assert [row.cutoff_date for row in rows] == [
        OPENING + timedelta(days=4),
        OPENING + timedelta(days=5),
    ]


def test_a_result_after_the_cutoff_changes_nothing(
    league: League, tmp_path: Path, postgres_session: Session
) -> None:
    model = EloModel(20, 100)
    register_model(postgres_session, _save(tmp_path, model, "elo"), activate=True)
    league.history("AAA", "BBB", 5)
    # Left unplayed, so the latest complete date stays at the last history game.
    league.game(OPENING + timedelta(days=6), "AAA", "BBB", "scheduled")
    game = league.game(date(2026, 12, 20), "AAA", "BBB", "scheduled")
    _publish(postgres_session, tmp_path)
    [first] = _rows(postgres_session, game)
    written = (first.cutoff_date, first.home_win_probability, first.inputs)

    league.game(OPENING + timedelta(days=9), "AAA", "BBB")
    league.game(OPENING + timedelta(days=10), "BBB", "AAA")
    postgres_session.execute(text("delete from ml.predictions"))
    _publish(postgres_session, tmp_path)

    [second] = _rows(postgres_session, game)
    assert (second.cutoff_date, second.home_win_probability, second.inputs) == written


def test_register_is_idempotent_and_moves_the_active_flag(
    tmp_path: Path, postgres_session: Session
) -> None:
    first_model, second_model = HomeRateModel(), HomeRateModel()
    first_model.home_rate, second_model.home_rate = 0.6, 0.7
    first = _save(tmp_path, first_model, "home-rate")
    second = _save(tmp_path, second_model, "home-rate")

    assert register_model(postgres_session, first, activate=True).created
    assert not register_model(postgres_session, first).created
    assert register_model(postgres_session, second, activate=True).is_active

    active = postgres_session.scalars(select(ModelVersion.name).where(ModelVersion.is_active)).all()
    total = postgres_session.scalar(select(func.count()).select_from(ModelVersion))
    assert active == [second.name]
    assert total == 2


def test_without_an_active_model_nothing_is_written(
    league: League, tmp_path: Path, postgres_session: Session
) -> None:
    with pytest.raises(PredictionError, match="no model is active"):
        _publish(postgres_session, tmp_path)


def test_an_empty_window_is_an_error(
    league: League, artifact: Path, tmp_path: Path, postgres_session: Session
) -> None:
    league.history("AAA", "BBB", 5)

    with pytest.raises(PredictionError, match="no game is dated"):
        _publish(postgres_session, tmp_path)
