from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from nba_data.config.settings import Settings, get_settings


def create_db_engine(settings: Settings | None = None) -> Engine:
    resolved_settings = settings or get_settings()
    return create_engine(resolved_settings.database_url, pool_pre_ping=True)


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    resolved_engine = engine or create_db_engine()
    return sessionmaker(bind=resolved_engine, autoflush=False, expire_on_commit=False)


def get_session(settings: Settings | None = None) -> Generator[Session, None, None]:
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        yield session
