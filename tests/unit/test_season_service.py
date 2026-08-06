from types import SimpleNamespace

import pytest

from nba_data.api.services import seasons as season_service


def _season(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 11,
        "season_year": 2024,
        "league": "NBA",
        "label": "2024",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.unit
def test_list_seasons_maps_only_the_public_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, object] = {}
    seasons = [_season(), _season(id=12, season_year=2023, label=None, secret="hidden")]

    def fake_count(session: object) -> int:
        received["count_session"] = session
        return 4

    def fake_list(session: object, *, offset: int, limit: int) -> list[SimpleNamespace]:
        received["list_session"] = session
        received["offset"] = offset
        received["limit"] = limit
        return seasons

    monkeypatch.setattr(season_service.season_queries, "count_seasons", fake_count)
    monkeypatch.setattr(season_service.season_queries, "list_seasons", fake_list)

    session = object()
    response = season_service.list_seasons(session, page=2, page_size=2)  # type: ignore[arg-type]

    assert received == {
        "count_session": session,
        "list_session": session,
        "offset": 2,
        "limit": 2,
    }
    assert response.model_dump() == {
        "items": [
            {"season_year": 2024, "league": "NBA", "label": "2024"},
            {"season_year": 2023, "league": "NBA", "label": None},
        ],
        "page": 2,
        "page_size": 2,
        "total": 4,
    }


@pytest.mark.unit
def test_list_seasons_preserves_valid_empty_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(season_service.season_queries, "count_seasons", lambda session: 1)
    monkeypatch.setattr(
        season_service.season_queries,
        "list_seasons",
        lambda session, *, offset, limit: [],
    )

    response = season_service.list_seasons(object(), page=99, page_size=50)  # type: ignore[arg-type]

    assert response.items == []
    assert response.page == 99
    assert response.page_size == 50
    assert response.total == 1


@pytest.mark.unit
def test_get_season_maps_existing_season_and_returns_none_for_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    season = _season()
    requested: list[int] = []

    def fake_get(session: object, season_year: int) -> SimpleNamespace | None:
        requested.append(season_year)
        return season if season_year == 2024 else None

    monkeypatch.setattr(season_service.season_queries, "get_season", fake_get)

    response = season_service.get_season(object(), season_year=2024)  # type: ignore[arg-type]

    assert response is not None
    assert response.model_dump() == {"season_year": 2024, "league": "NBA", "label": "2024"}
    assert season_service.get_season(object(), season_year=1800) is None  # type: ignore[arg-type]
    assert requested == [2024, 1800]
