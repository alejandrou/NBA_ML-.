import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from nba_data.api.routers.health import router as health_router
from nba_data.api.routers.seasons import router as seasons_router
from nba_data.api.routers.teams import router as teams_router
from nba_data.config.logging_config import configure_logging
from nba_data.config.settings import get_settings
from nba_data.db.session import create_db_engine, create_session_factory

API_V1_PREFIX = "/api/v1"

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging(get_settings())
    engine = create_db_engine()
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    try:
        yield
    finally:
        engine.dispose()


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Return the documented error body instead of Starlette's plain-text default."""
    logger.exception("Unhandled error serving %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


def create_app() -> FastAPI:
    app = FastAPI(
        title="NBA Data API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_exception_handler(Exception, handle_unexpected_error)

    api_router = APIRouter()
    api_router.include_router(health_router)
    api_router.include_router(teams_router)
    api_router.include_router(seasons_router)
    app.include_router(api_router, prefix=API_V1_PREFIX)

    return app
