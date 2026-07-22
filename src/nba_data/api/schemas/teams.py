from pydantic import BaseModel


class TeamResponse(BaseModel):
    team_id: int
    basketball_reference_team_id: str | None
    current_abbreviation: str | None
    current_name: str
    franchise_id: str | None


class TeamListResponse(BaseModel):
    items: list[TeamResponse]
    page: int
    page_size: int
    total: int
