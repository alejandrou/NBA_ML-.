from pydantic import BaseModel


class SeasonResponse(BaseModel):
    season_year: int
    league: str
    label: str | None


class SeasonListResponse(BaseModel):
    items: list[SeasonResponse]
    page: int
    page_size: int
    total: int
