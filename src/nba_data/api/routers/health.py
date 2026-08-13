from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from nba_data.api.dependencies import get_request_session
from nba_data.api.schemas.health import (
    HealthResponse,
    ReadinessErrorResponse,
    ReadinessResponse,
)
from nba_data.api.services import readiness as readiness_service
from nba_data.api.services.readiness import ReadinessOutcome
from nba_data.config.settings import Settings, get_settings

router = APIRouter(tags=["health"])

SessionDependency = Annotated[Session, Depends(get_request_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]

NOT_READY_DETAIL: dict[ReadinessOutcome, str] = {
    ReadinessOutcome.UNAVAILABLE: "Database unavailable",
    ReadinessOutcome.TIMED_OUT: "Database readiness check timed out",
    ReadinessOutcome.SCHEMA_NOT_READY: "Database schema not ready",
}


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check API liveness",
)
def get_health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Check database readiness",
    responses={
        503: {
            "model": ReadinessErrorResponse,
            "description": "The database is not ready to serve data",
        }
    },
)
def get_readiness(
    session: SessionDependency,
    settings: SettingsDependency,
) -> ReadinessResponse:
    outcome = readiness_service.check_database_readiness(
        session, timeout_seconds=settings.api_readiness_timeout_seconds
    )
    if outcome is not ReadinessOutcome.READY:
        raise HTTPException(status_code=503, detail=NOT_READY_DETAIL[outcome])
    return ReadinessResponse(status="ready")
