from pydantic import BaseModel


class TeamResponse(BaseModel):
    basketball_reference_team_id: str
    current_abbreviation: str | None
    current_name: str


class TeamListResponse(BaseModel):
    items: list[TeamResponse]
    page: int
    page_size: int
    total: int
