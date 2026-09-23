from pydantic import BaseModel


class PlayerResponse(BaseModel):
    basketball_reference_player_id: str
    full_name: str


class PlayerListResponse(BaseModel):
    items: list[PlayerResponse]
    page: int
    page_size: int
    total: int


class PlayerSeasonResponse(BaseModel):
    season_year: int
    league: str
    teams: list[str]


class PlayerSeasonListResponse(BaseModel):
    items: list[PlayerSeasonResponse]
    page: int
    page_size: int
    total: int
