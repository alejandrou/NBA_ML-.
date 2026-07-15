from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from nba_data.api.routers.health import router as health_router

API_V1_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="NBA Data API",
        version="0.1.0",
        lifespan=lifespan,
    )

    api_router = APIRouter()
    api_router.include_router(health_router)
    app.include_router(api_router, prefix=API_V1_PREFIX)

    return app
