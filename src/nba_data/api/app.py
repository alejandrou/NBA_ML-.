from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from nba_data.api.routers.health import router as health_router
from nba_data.db.session import create_db_engine, create_session_factory

API_V1_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_db_engine()
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    try:
        yield
    finally:
        engine.dispose()


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
