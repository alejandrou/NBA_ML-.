from types import SimpleNamespace

import pytest

from nba_data.api.services import players as player_service
from nba_data.api.services.players import PlayerNotFoundError, PlayerSeasonNotFoundError
from nba_data.db.repositories.queries.players import PlayerSeasonIdentity


def _player(**overrides: object) -> SimpleNamespace:
    """A stand-in row carrying no surrogate id or slug, because the response has neither.

    Leaving them out means a mapping that started reading one would fail here
    rather than quietly pass on a value the contract keeps private.
    """
    values: dict[str, object] = {
        "basketball_reference_player_id": "jamesle01",
        "full_name": "LeBron James",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _known_players(monkeypatch: pytest.MonkeyPatch, *known: str) -> list[str]:
    requested: list[str] = []

    def fake_get(session: object, basketball_reference_player_id: str) -> SimpleNamespace | None:
        requested.append(basketball_reference_player_id)
        if basketball_reference_player_id in known:
            return _player(basketball_reference_player_id=basketball_reference_player_id)
        return None

    monkeypatch.setattr(player_service.player_queries, "get_player", fake_get)
    return requested


@pytest.mark.unit
def test_list_players_maps_only_the_public_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    received: dict[str, object] = {}
    players = [
        _player(),
        _player(basketball_reference_player_id="smithjo01", full_name="John Smith", slug="x"),
    ]

    def fake_count(session: object) -> int:
        received["count_session"] = session
        return 7

    def fake_list(session: object, *, offset: int, limit: int) -> list[SimpleNamespace]:
        received["list_session"] = session
        received["offset"] = offset
        received["limit"] = limit
        return players

    monkeypatch.setattr(player_service.player_queries, "count_players", fake_count)
    monkeypatch.setattr(player_service.player_queries, "list_players", fake_list)

    session = object()
    response = player_service.list_players(session, page=3, page_size=2)  # type: ignore[arg-type]

    assert received == {"count_session": session, "list_session": session, "offset": 4, "limit": 2}
    assert response.model_dump() == {
        "items": [
            {"basketball_reference_player_id": "jamesle01", "full_name": "LeBron James"},
            {"basketball_reference_player_id": "smithjo01", "full_name": "John Smith"},
        ],
        "page": 3,
        "page_size": 2,
        "total": 7,
    }


@pytest.mark.unit
def test_a_player_without_an_id_is_never_mapped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(player_service.player_queries, "count_players", lambda session: 1)
    monkeypatch.setattr(
        player_service.player_queries,
        "list_players",
        lambda session, *, offset, limit: [_player(basketball_reference_player_id=None)],
    )

    with pytest.raises(ValueError):
        player_service.list_players(object(), page=1, page_size=50)  # type: ignore[arg-type]


@pytest.mark.unit
def test_get_player_maps_a_known_player_and_raises_for_an_unknown_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requested = _known_players(monkeypatch, "jamesle01")

    response = player_service.get_player(  # type: ignore[arg-type]
        object(), basketball_reference_player_id="jamesle01"
    )

    assert response.model_dump() == {
        "basketball_reference_player_id": "jamesle01",
        "full_name": "LeBron James",
    }
    with pytest.raises(PlayerNotFoundError):
        player_service.get_player(  # type: ignore[arg-type]
            object(), basketball_reference_player_id="JAMESLE01"
        )
    assert requested == ["jamesle01", "JAMESLE01"]


@pytest.mark.unit
def test_list_player_seasons_pages_a_known_player(monkeypatch: pytest.MonkeyPatch) -> None:
    _known_players(monkeypatch, "jamesle01")
    received: dict[str, object] = {}

    def fake_count(session: object, basketball_reference_player_id: str) -> int:
        received["count"] = basketball_reference_player_id
        return 3

    def fake_list(
        session: object, basketball_reference_player_id: str, *, offset: int, limit: int
    ) -> list[PlayerSeasonIdentity]:
        received["list"] = (basketball_reference_player_id, offset, limit)
        return [PlayerSeasonIdentity(season_year=2004, league="NBA", teams=("CLE", "MIA"))]

    monkeypatch.setattr(player_service.player_queries, "count_player_seasons", fake_count)
    monkeypatch.setattr(player_service.player_queries, "list_player_seasons", fake_list)

    response = player_service.list_player_seasons(  # type: ignore[arg-type]
        object(), basketball_reference_player_id="jamesle01", page=2, page_size=1
    )

    assert received == {"count": "jamesle01", "list": ("jamesle01", 1, 1)}
    assert response.model_dump() == {
        "items": [{"season_year": 2004, "league": "NBA", "teams": ["CLE", "MIA"]}],
        "page": 2,
        "page_size": 1,
        "total": 3,
    }


@pytest.mark.unit
def test_list_player_seasons_of_a_player_with_none_is_an_empty_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _known_players(monkeypatch, "rookiaa01")
    monkeypatch.setattr(
        player_service.player_queries, "count_player_seasons", lambda session, pid: 0
    )
    monkeypatch.setattr(
        player_service.player_queries,
        "list_player_seasons",
        lambda session, pid, *, offset, limit: [],
    )

    response = player_service.list_player_seasons(  # type: ignore[arg-type]
        object(), basketball_reference_player_id="rookiaa01", page=1, page_size=50
    )

    assert response.model_dump() == {"items": [], "page": 1, "page_size": 50, "total": 0}


@pytest.mark.unit
def test_list_player_seasons_of_an_unknown_player_raises_before_reading_seasons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _known_players(monkeypatch)

    def must_not_run(*args: object, **kwargs: object) -> object:
        raise AssertionError("seasons were read for an unknown player")

    monkeypatch.setattr(player_service.player_queries, "count_player_seasons", must_not_run)
    monkeypatch.setattr(player_service.player_queries, "list_player_seasons", must_not_run)

    with pytest.raises(PlayerNotFoundError):
        player_service.list_player_seasons(  # type: ignore[arg-type]
            object(), basketball_reference_player_id="unknown01", page=1, page_size=50
        )


@pytest.mark.unit
def test_get_player_season_distinguishes_a_missing_player_from_a_missing_season(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _known_players(monkeypatch, "jamesle01")

    def fake_get_season(
        session: object, basketball_reference_player_id: str, season_year: int
    ) -> PlayerSeasonIdentity | None:
        if season_year == 2005:
            return PlayerSeasonIdentity(season_year=2005, league="NBA", teams=())
        return None

    monkeypatch.setattr(player_service.player_queries, "get_player_season", fake_get_season)

    response = player_service.get_player_season(  # type: ignore[arg-type]
        object(), basketball_reference_player_id="jamesle01", season_year=2005
    )

    assert response.model_dump() == {"season_year": 2005, "league": "NBA", "teams": []}
    with pytest.raises(PlayerSeasonNotFoundError):
        player_service.get_player_season(  # type: ignore[arg-type]
            object(), basketball_reference_player_id="jamesle01", season_year=1999
        )
    with pytest.raises(PlayerNotFoundError):
        player_service.get_player_season(  # type: ignore[arg-type]
            object(), basketball_reference_player_id="unknown01", season_year=2005
        )
