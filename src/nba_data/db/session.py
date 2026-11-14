import os
from collections.abc import Collection, Generator
from contextlib import nullcontext
from math import ceil

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, Connection, make_url
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


def read_only_connect_options(
    statement_timeout_seconds: float, existing_options: str | None = None
) -> str:
    """libpq `options` that make every API connection read-only and time-bounded.

    The API's read-only guarantee is otherwise code-level only (ADR 0021): this
    makes PostgreSQL refuse a write as well. The same bound applies to a statement
    and to a transaction left idle, so one pathological request cannot hold a
    pooled connection indefinitely. The readiness probe still narrows its own
    statement with `SET LOCAL`.

    `existing_options` (the URL's or `PGOPTIONS`) are kept, ahead of these: the
    server applies `-c` settings in order, so ours win on a conflict while
    `search_path`, `TimeZone` or `application_name` survive.
    """
    milliseconds = max(1, ceil(statement_timeout_seconds * 1000))
    mandatory = (
        "-c default_transaction_read_only=on"
        f" -c statement_timeout={milliseconds}"
        f" -c idle_in_transaction_session_timeout={milliseconds}"
    )
    existing = (existing_options or "").strip()
    return f"{existing} {mandatory}" if existing else mandatory


def _existing_connect_options(url: URL) -> str | None:
    """The libpq `options` a connection would otherwise use: the URL's, else `PGOPTIONS`.

    Passing `options` explicitly replaces both, so they are read here and merged.
    """
    value = url.query.get("options")
    if isinstance(value, tuple):
        return " ".join(value)
    if value is not None:
        return value
    return os.environ.get("PGOPTIONS")


def create_api_engine(settings: Settings | None = None) -> Engine:
    """The read-only API's engine: every connection opens read-only and time-bounded."""
    resolved_settings = settings or get_settings()
    url = make_url(resolved_settings.database_url)
    connect_args = connect_args_for(url, resolved_settings.database_connect_timeout_seconds)
    if url.get_backend_name() == "postgresql":
        connect_args["options"] = read_only_connect_options(
            resolved_settings.api_statement_timeout_seconds, _existing_connect_options(url)
        )
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


# A bulk load writes these schemas; `ml` is written by its own jobs and analyzed there.
LOADED_SCHEMAS: tuple[str, ...] = ("core", "stats")
ANALYZE_STATEMENT_TIMEOUT_SECONDS = 600
ANALYZE_LOCK_TIMEOUT_SECONDS = 10


def analyze_database(
    bind: Engine | Connection,
    schemas: Collection[str] = LOADED_SCHEMAS,
    *,
    statement_timeout_seconds: float = ANALYZE_STATEMENT_TIMEOUT_SECONDS,
    lock_timeout_seconds: float = ANALYZE_LOCK_TIMEOUT_SECONDS,
) -> bool:
    """Refresh PostgreSQL planner statistics for the tables a load wrote.

    Autovacuum only analyzes a table after enough changes since its counters
    were last reset, so after an unclean restart a freshly loaded table can
    keep stale estimates indefinitely (DATABASE_AUDIT_2026-11-10, H-10).

    Only the tables in `schemas` are analyzed, and the statement is bounded: a
    lock held by concurrent maintenance or DDL fails it after
    `lock_timeout_seconds` instead of delaying the report of a committed load.
    Returns False, doing nothing, for any other database. Given a Connection
    (a load's locked one), it runs there and commits; given an Engine, on a
    connection of its own.
    """
    if bind.dialect.name != "postgresql":
        return False
    with bind.connect() if isinstance(bind, Engine) else nullcontext(bind) as connection:
        tables = (
            connection.execute(
                text(
                    "SELECT format('%I.%I', schemaname, tablename) FROM pg_catalog.pg_tables "
                    "WHERE schemaname = ANY(:schemas) ORDER BY 1"
                ),
                {"schemas": sorted(schemas)},
            )
            .scalars()
            .all()
        )
        if not tables:
            connection.rollback()
            return True
        connection.execute(
            text("SELECT set_config('statement_timeout', :value, true)"),
            {"value": f"{max(1, ceil(statement_timeout_seconds * 1000))}ms"},
        )
        connection.execute(
            text("SELECT set_config('lock_timeout', :value, true)"),
            {"value": f"{max(1, ceil(lock_timeout_seconds * 1000))}ms"},
        )
        # Names come from the catalog, quoted by format('%I').
        connection.execute(text(f"ANALYZE {', '.join(tables)}"))
        connection.commit()
    return True


def create_session_factory(
    bind: Engine | Connection | None = None,
) -> sessionmaker[Session]:
    """Sessions on `bind`. A load passes its locked Connection, so that its
    sessions' commits are that connection's commits (R-02)."""
    resolved_bind = bind if bind is not None else create_db_engine()
    return sessionmaker(bind=resolved_bind, autoflush=False, expire_on_commit=False)


def get_session(settings: Settings | None = None) -> Generator[Session, None, None]:
    engine = create_db_engine(settings)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        yield session
