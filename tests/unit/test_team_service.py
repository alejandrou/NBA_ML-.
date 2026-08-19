from types import SimpleNamespace

import pytest

from nba_data.api.services import teams as team_service


def _team(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 7,
        "basketball_reference_team_id": "ATL",
        "current_abbreviation": "ATL",
        "current_name": "Atlanta Hawks",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.unit
def test_list_teams_maps_only_the_public_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, object] = {}
    teams = [_team(), _team(id=9, current_name="Boston Celtics", secret="hidden")]

    def fake_count(session: object) -> int:
        received["count_session"] = session
        return 4

    def fake_list(session: object, *, offset: int, limit: int) -> list[SimpleNamespace]:
        received["list_session"] = session
        received["offset"] = offset
        received["limit"] = limit
        return teams

    monkeypatch.setattr(team_service.team_queries, "count_teams", fake_count)
    monkeypatch.setattr(team_service.team_queries, "list_teams", fake_list)

    session = object()
    response = team_service.list_teams(session, page=2, page_size=2)  # type: ignore[arg-type]

    assert received == {
        "count_session": session,
        "list_session": session,
        "offset": 2,
        "limit": 2,
    }
    assert response.model_dump() == {
        "items": [
            {
                "basketball_reference_team_id": "ATL",
                "current_abbreviation": "ATL",
                "current_name": "Atlanta Hawks",
            },
            {
                "basketball_reference_team_id": "ATL",
                "current_abbreviation": "ATL",
                "current_name": "Boston Celtics",
            },
        ],
        "page": 2,
        "page_size": 2,
        "total": 4,
    }


@pytest.mark.unit
def test_list_teams_preserves_valid_empty_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(team_service.team_queries, "count_teams", lambda session: 1)
    monkeypatch.setattr(
        team_service.team_queries,
        "list_teams",
        lambda session, *, offset, limit: [],
    )

    response = team_service.list_teams(object(), page=99, page_size=50)  # type: ignore[arg-type]

    assert response.items == []
    assert response.page == 99
    assert response.page_size == 50
    assert response.total == 1


@pytest.mark.unit
def test_get_team_maps_existing_team_and_returns_none_for_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    team = _team()
    requested: list[str] = []

    def fake_get(session: object, basketball_reference_team_id: str) -> SimpleNamespace | None:
        requested.append(basketball_reference_team_id)
        return team if basketball_reference_team_id == "ATL" else None

    monkeypatch.setattr(
        team_service.team_queries,
        "get_team_by_basketball_reference_team_id",
        fake_get,
    )

    response = team_service.get_team(  # type: ignore[arg-type]
        object(),
        basketball_reference_team_id="ATL",
    )

    assert response is not None
    assert response.basketball_reference_team_id == "ATL"
    assert (
        team_service.get_team(  # type: ignore[arg-type]
            object(),
            basketball_reference_team_id="atl",
        )
        is None
    )
    assert requested == ["ATL", "atl"]
