from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadinessResponse(BaseModel):
    status: Literal["ready"]


class ReadinessErrorResponse(BaseModel):
    """The three fixed not-ready bodies; none of them ever varies with the cause."""

    detail: Literal[
        "Database unavailable",
        "Database readiness check timed out",
        "Database schema not ready",
    ]
