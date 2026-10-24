"""The statistics routes, one literal route per served season type, grain, and family.

Each route carries its family's own `response_model`, so OpenAPI publishes a
distinct, fully typed body per family instead of an untyped union. The two
hidden catch-all routes come last: they only turn an unrecognized
`{season_type}` or `{family}` into the contract's 422, and a recognized but
unserved combination into a 404.
"""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query

from nba_data.api.routers.players import (
    PLAYER_NOT_FOUND,
    PLAYER_SEASON_NOT_FOUND,
    PlayerIdPath,
    SeasonYearPath,
    SessionDependency,
)
from nba_data.api.schemas.player_stats import (
    STAT_BODIES,
    AggregateStatIdentity,
    StintStatListResponse,
)
from nba_data.api.services import player_stats as stat_service
from nba_data.api.services.player_stats import StatisticsNotFoundError
from nba_data.api.services.players import PlayerNotFoundError, PlayerSeasonNotFoundError
from nba_data.domain.stat_dimensions import SeasonType, StatFamily

router = APIRouter(prefix="/players", tags=["player statistics"])

# Fixed string: it never interpolates the id, the year, the family, or an exception.
STATISTICS_NOT_FOUND = "Statistics not found"
# The framework's own body for a path no route serves.
NOT_SERVED = "Not Found"

_PLAYER_SEASON_PATH = "/{basketball_reference_player_id}/seasons/{season_year}"
_SEASON_TYPE_LABELS = {SeasonType.REGULAR: "regular-season", SeasonType.POSTSEASON: "postseason"}


def _aggregate_route(
    season_type: SeasonType, family: StatFamily
) -> Callable[..., AggregateStatIdentity]:
    def get_aggregate_stats(
        basketball_reference_player_id: PlayerIdPath,
        season_year: SeasonYearPath,
        session: SessionDependency,
    ) -> AggregateStatIdentity:
        try:
            return stat_service.get_aggregate_stats(
                session,
                basketball_reference_player_id=basketball_reference_player_id,
                season_year=season_year,
                season_type=season_type,
                family=family,
            )
        except PlayerNotFoundError:
            raise HTTPException(status_code=404, detail=PLAYER_NOT_FOUND) from None
        except PlayerSeasonNotFoundError:
            raise HTTPException(status_code=404, detail=PLAYER_SEASON_NOT_FOUND) from None
        except StatisticsNotFoundError:
            raise HTTPException(status_code=404, detail=STATISTICS_NOT_FOUND) from None

    return get_aggregate_stats


def _stint_route(
    season_type: SeasonType, family: StatFamily
) -> Callable[..., StintStatListResponse[Any]]:
    def list_stint_stats(
        basketball_reference_player_id: PlayerIdPath,
        season_year: SeasonYearPath,
        session: SessionDependency,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> StintStatListResponse[Any]:
        try:
            return stat_service.list_stint_stats(
                session,
                basketball_reference_player_id=basketball_reference_player_id,
                season_year=season_year,
                season_type=season_type,
                family=family,
                page=page,
                page_size=page_size,
            )
        except PlayerNotFoundError:
            raise HTTPException(status_code=404, detail=PLAYER_NOT_FOUND) from None
        except PlayerSeasonNotFoundError:
            raise HTTPException(status_code=404, detail=PLAYER_SEASON_NOT_FOUND) from None

    return list_stint_stats


for _season_type in stat_service.SERVED_SEASON_TYPES:
    for _family in StatFamily:
        _aggregate_body, _stint_body = STAT_BODIES[_family]
        _label = f"{_SEASON_TYPE_LABELS[_season_type]} {_family.value}"
        router.add_api_route(
            f"{_PLAYER_SEASON_PATH}/{_season_type.value}/aggregate/{_family.value}",
            _aggregate_route(_season_type, _family),
            methods=["GET"],
            response_model=_aggregate_body,
            name=f"get_{_season_type.value}_aggregate_{_family.value}",
            summary=f"Get a player's {_label} aggregate",
        )
        router.add_api_route(
            f"{_PLAYER_SEASON_PATH}/{_season_type.value}/stints/{_family.value}",
            _stint_route(_season_type, _family),
            methods=["GET"],
            response_model=_stint_body,
            name=f"list_{_season_type.value}_stints_{_family.value}",
            summary=f"List a player's {_label} stints",
        )


@router.get(
    _PLAYER_SEASON_PATH + "/{season_type}/aggregate/{family}",
    include_in_schema=False,
)
def reject_unserved_aggregate(
    basketball_reference_player_id: PlayerIdPath,
    season_year: SeasonYearPath,
    season_type: SeasonType,
    family: StatFamily,
) -> None:
    raise HTTPException(status_code=404, detail=NOT_SERVED)


@router.get(
    _PLAYER_SEASON_PATH + "/{season_type}/stints/{family}",
    include_in_schema=False,
)
def reject_unserved_stints(
    basketball_reference_player_id: PlayerIdPath,
    season_year: SeasonYearPath,
    season_type: SeasonType,
    family: StatFamily,
) -> None:
    raise HTTPException(status_code=404, detail=NOT_SERVED)
