"""The `ml` constraints behave on PostgreSQL, each proven by the name it reports."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration

Probe = tuple[str, dict[str, object]]


@pytest.fixture
def game_id(postgres_connection: Connection) -> int:
    connection = postgres_connection
    season = _scalar(
        connection,
        "insert into core.seasons (season_year, league) values (-1, 'ML-PROBE') returning id",
    )
    home, away = (_team_season(connection, season, code) for code in ("HMX", "AWX"))
    return _scalar(
        connection,
        "insert into core.games (basketball_reference_game_id, season_id, home_team_season_id, "
        "away_team_season_id, game_date, status) values "
        "('202612010HMX', :season, :home, :away, '2026-12-01', 'scheduled') returning id",
        {"season": season, "home": home, "away": away},
    )


@pytest.fixture
def version_id(postgres_connection: Connection) -> int:
    return _scalar(postgres_connection, *_version())


def _version(**overrides: object) -> Probe:
    unique = uuid4().hex
    values: dict[str, object] = {
        "name": f"probe-{unique}",
        "model_family": "logistic",
        "feature_definition_version": "team-pregame-v1",
        "artifact_sha256": (unique * 2)[:64],
        "is_active": False,
        **overrides,
    }
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    return (
        f"insert into ml.model_versions ({columns}, training_seasons, configuration, metrics) "
        f"values ({placeholders}, '{{2026}}', '{{}}', '{{}}') returning id",
        values,
    )


def _prediction(game_id: int, version_id: int, **overrides: object) -> Probe:
    values: dict[str, object] = {
        "game_id": game_id,
        "model_version_id": version_id,
        "cutoff_date": date(2026, 11, 29),
        "status": "available",
        "unavailable_reason": None,
        "home_win_probability": "0.600000",
        "away_win_probability": "0.400000",
        "favorite": "home",
        **overrides,
    }
    columns = ", ".join(values)
    placeholders = ", ".join(f":{key}" for key in values)
    return (
        f"insert into ml.predictions ({columns}, inputs) "
        f"values ({placeholders}, '{{}}') returning id",
        values,
    )


UNAVAILABLE: dict[str, object] = {
    "status": "unavailable",
    "unavailable_reason": "insufficient_history",
    "home_win_probability": None,
    "away_win_probability": None,
    "favorite": None,
}


def test_a_valid_forecast_and_a_valid_unavailable_row_are_accepted(
    postgres_connection: Connection, game_id: int, version_id: int
) -> None:
    _scalar(postgres_connection, *_prediction(game_id, version_id))
    _scalar(
        postgres_connection,
        *_prediction(game_id, version_id, cutoff_date=date(2026, 11, 28), **UNAVAILABLE),
    )


def test_availability_is_false_by_default(
    postgres_connection: Connection, game_id: int, version_id: int
) -> None:
    row_id = _scalar(postgres_connection, *_prediction(game_id, version_id))

    included = postgres_connection.execute(
        text("select availability_included from ml.predictions where id = :id"), {"id": row_id}
    ).scalar_one()
    assert included is False


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"away_win_probability": "0.500000"}, "ck_ml_predictions_probabilities_sum"),
        (
            {"home_win_probability": "1.100000", "away_win_probability": "-0.100000"},
            "ck_ml_predictions_probability_range",
        ),
        ({"favorite": "away"}, "ck_ml_predictions_favorite_rule"),
        ({"favorite": None}, "ck_ml_predictions_favorite_rule"),
        (
            {
                "home_win_probability": "0.500000",
                "away_win_probability": "0.500000",
                "favorite": "home",
            },
            "ck_ml_predictions_favorite_rule",
        ),
        ({"favorite": "draw"}, "ck_ml_predictions_favorite"),
        ({"status": "pending"}, "ck_ml_predictions_status"),
        (
            {"home_win_probability": None, "away_win_probability": None, "favorite": None},
            "ck_ml_predictions_status_fields",
        ),
        ({"unavailable_reason": "insufficient_history"}, "ck_ml_predictions_status_fields"),
    ],
)
def test_an_available_row_breaking_a_rule_is_refused(
    postgres_connection: Connection,
    game_id: int,
    version_id: int,
    overrides: dict[str, object],
    constraint: str,
) -> None:
    probe = _prediction(game_id, version_id, **overrides)

    _assert_rejected_by(postgres_connection, probe, constraint)


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        (
            {
                "home_win_probability": "0.600000",
                "away_win_probability": "0.400000",
            },
            "ck_ml_predictions_status_fields",
        ),
        ({"favorite": "home"}, "ck_ml_predictions_status_fields"),
        ({"unavailable_reason": None}, "ck_ml_predictions_status_fields"),
        ({"unavailable_reason": "injured"}, "ck_ml_predictions_unavailable_reason"),
    ],
)
def test_an_unavailable_row_carries_a_reason_and_nothing_else(
    postgres_connection: Connection,
    game_id: int,
    version_id: int,
    overrides: dict[str, object],
    constraint: str,
) -> None:
    probe = _prediction(game_id, version_id, **(UNAVAILABLE | overrides))

    _assert_rejected_by(postgres_connection, probe, constraint)


@pytest.mark.parametrize(
    "reason", ["team_season_missing", "insufficient_history", "game_not_scheduled"]
)
def test_every_reason_of_the_set_is_accepted(
    postgres_connection: Connection, game_id: int, version_id: int, reason: str
) -> None:
    _scalar(
        postgres_connection,
        *_prediction(game_id, version_id, **(UNAVAILABLE | {"unavailable_reason": reason})),
    )


def test_a_forecast_is_unique_per_game_model_and_cutoff(
    postgres_connection: Connection, game_id: int, version_id: int
) -> None:
    _scalar(postgres_connection, *_prediction(game_id, version_id))

    _assert_rejected_by(
        postgres_connection,
        _prediction(game_id, version_id),
        "uq_ml_predictions_game_model_cutoff",
    )


def test_only_one_model_is_active(postgres_connection: Connection) -> None:
    _scalar(postgres_connection, *_version(is_active=True))

    _assert_rejected_by(
        postgres_connection, _version(is_active=True), "uq_ml_model_versions_single_active"
    )


def test_many_models_can_be_inactive(postgres_connection: Connection) -> None:
    _scalar(postgres_connection, *_version())
    _scalar(postgres_connection, *_version())


def test_a_malformed_hash_is_refused(postgres_connection: Connection) -> None:
    _assert_rejected_by(
        postgres_connection,
        _version(artifact_sha256="ABC"),
        "ck_ml_model_versions_sha256_format",
    )


def test_a_hash_is_registered_once(postgres_connection: Connection) -> None:
    sha256 = "a" * 64
    _scalar(postgres_connection, *_version(artifact_sha256=sha256))

    _assert_rejected_by(
        postgres_connection,
        _version(artifact_sha256=sha256),
        "uq_ml_model_versions_artifact_sha256",
    )


def _assert_rejected_by(connection: Connection, probe: Probe, constraint: str) -> None:
    statement, parameters = probe
    savepoint = connection.begin_nested()
    error: IntegrityError | None = None
    try:
        connection.execute(text(statement), parameters)
    except IntegrityError as caught:
        error = caught
    finally:
        savepoint.rollback()

    assert error is not None, f"{constraint} accepted {parameters!r}"
    violated = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
    assert violated == constraint


def _team_season(connection: Connection, season: int, code: str) -> int:
    team = _scalar(
        connection,
        "insert into core.teams (basketball_reference_team_id, current_name) "
        "values (:code, 'ML probe') returning id",
        {"code": code},
    )
    return _scalar(
        connection,
        "insert into core.team_seasons (team_id, season_id, team_abbreviation) "
        "values (:team, :season, :code) returning id",
        {"team": team, "season": season, "code": code},
    )


def _scalar(
    connection: Connection, statement: str, parameters: dict[str, object] | None = None
) -> int:
    return int(connection.execute(text(statement), parameters or {}).scalar_one())
