import pytest

from nba_data.validation.team_season import (
    TeamSeasonDataQualityError,
    assert_valid_normalized_team_season_rows,
    validate_normalized_team_season_rows,
)


@pytest.mark.unit
def test_validate_normalized_team_season_rows_accepts_valid_player_row() -> None:
    issues = validate_normalized_team_season_rows([_row()])

    assert issues == []


@pytest.mark.unit
def test_validate_normalized_team_season_rows_reports_missing_context() -> None:
    row = _row()
    del row["source_table"]

    issues = validate_normalized_team_season_rows([row])

    assert issues[0].code == "missing_context"
    assert "source_table" in issues[0].message


@pytest.mark.unit
def test_validate_normalized_team_season_rows_reports_tot_team_misuse() -> None:
    row = _row(team_abbreviation="TOT", team_context="team")

    issues = validate_normalized_team_season_rows([row])

    assert {issue.code for issue in issues} == {"tot_not_aggregate"}
    assert "TOT rows must be classified" in issues[0].message


@pytest.mark.unit
def test_validate_normalized_team_season_rows_reports_missing_player_id() -> None:
    row = _row(
        player_name="Missing Id",
        basketball_reference_player_id=None,
        stable_player_key=None,
        identifier_status="missing_player_id",
    )

    issues = validate_normalized_team_season_rows([row])

    assert issues[0].code == "missing_player_id"
    assert "do not use player_name" in issues[0].message


@pytest.mark.unit
def test_validate_normalized_team_season_rows_reports_duplicate_natural_key() -> None:
    issues = validate_normalized_team_season_rows([_row(), _row()])

    assert issues[0].code == "duplicate_natural_key"
    assert "first seen at row 0" in issues[0].message


@pytest.mark.unit
def test_validate_normalized_team_season_rows_reports_required_empty_table() -> None:
    issues = validate_normalized_team_season_rows([_row()], required_tables={"advanced"})

    assert issues[0].code == "required_table_empty"
    assert "advanced" in issues[0].message


@pytest.mark.unit
def test_assert_valid_normalized_team_season_rows_raises_actionable_error() -> None:
    row = _row(basketball_reference_player_id=None, stable_player_key=None)

    with pytest.raises(TeamSeasonDataQualityError, match="missing basketball_reference_player_id"):
        assert_valid_normalized_team_season_rows([row])


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "league": "NBA",
        "season_year": 2024,
        "team_abbreviation": "BOS",
        "team_context": "team",
        "source_table": "totals",
        "stat_scope": "player_team_season",
        "player_name": "Jayson Tatum",
        "basketball_reference_player_id": "tatumja01",
        "stable_player_key": "tatumja01",
        "identifier_status": "present",
        "values": {"games": 74},
    }
    row.update(overrides)
    return row
