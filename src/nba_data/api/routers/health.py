from fastapi import APIRouter

from nba_data.api.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API liveness",
)
def get_health() -> HealthResponse:
    return HealthResponse(status="ok")
