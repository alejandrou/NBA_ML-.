from collections.abc import Generator
from math import ceil

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session, sessionmaker

from nba_data.config.settings import Settings, get_settings

# libpq takes whole seconds and silently raises anything below 2 to 2, so the
# floor is stated here rather than left as a surprise in the driver.
LIBPQ_MINIMUM_CONNECT_TIMEOUT_SECONDS = 2


def connect_args_for(url: URL, connect_timeout_seconds: float) -> dict[str, object]:
    """Bound connection establishment, which no statement-level timeout can cover.

    `statement_timeout` only starts once a connection exists. Without this, a host
    that swallows packets leaves psycopg waiting indefinitely, so a readiness probe
    hangs instead of answering 503.
    """
    if url.get_backend_name() != "postgresql":
        return {}

    seconds = max(LIBPQ_MINIMUM_CONNECT_TIMEOUT_SECONDS, ceil(connect_timeout_seconds))
    return {"connect_timeout": seconds}


def create_db_engine(settings: Settings | None = None) -> Engine:
    resolved_settings = settings or get_settings()
    url = make_url(resolved_settings.database_url)
    return create_engine(
        url,
        pool_pre_ping=True,
        connect_args=connect_args_for(url, resolved_settings.database_connect_timeout_seconds),
    )


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    resolved_engine = engine or create_db_engine()
    return sessionmaker(bind=resolved_engine, autoflush=False, expire_on_commit=False)


def get_session(settings: Settings | None = None) -> Generator[Session, None, None]:
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        yield session
