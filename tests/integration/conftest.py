"""Shared PostgreSQL policy and lifecycle for the integration lane.

Two things live here and nowhere else.

**Authorization.** A test in this directory may only reach a database that the
operator has explicitly volunteered as disposable. That takes both an exact
opt-in flag and a database name from the approved disposable set. Both are
decided *before* an Engine exists, so a misconfigured run cannot touch a real
database even by accident: the skip and fail branches below never construct an
Engine, never connect, and never issue a statement.

**Isolation.** Every database-mutating test runs inside one outer transaction
that the fixture rolls back unconditionally. Sessions join it through savepoints
and therefore cannot commit it, which keeps the loader's caller-owned
transaction contract intact while leaving the database as it was found.

Setting `NBA_DATA_TEST_DATABASE=1` is a destructive-test authorization, not a
convenience setting. It says "the database this URL names is mine to fill and
throw away".
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from nba_data.api import create_app
from nba_data.api.dependencies import get_request_session
from nba_data.config.settings import get_settings

# Imported for its import side effect: every mapped model must be registered on
# the shared metadata before the empty-core guard derives its table list from
# it, or the guard silently checks a subset.
from nba_data.db import models as _models  # noqa: F401
from nba_data.db.base import Base

#: Fail-closed interlock. Must be exactly ``1`` after trimming — no truthy
#: spellings — because the cost of a false positive is writing to a real
#: database.
TEST_DATABASE_ENV = "NBA_DATA_TEST_DATABASE"
TEST_DATABASE_OPT_IN_VALUE = "1"

#: Strictness switch, which cannot cause a write on its own and so keeps the
#: repository's existing case-insensitive truthy convention.
REQUIRE_POSTGRES_INTEGRATION_ENV = "NBA_DATA_REQUIRE_POSTGRES_INTEGRATION"
REQUIRED_MODE_TRUTHY_VALUES = frozenset({"1", "true", "yes", "on"})

#: The CI service container, and the scratch databases
#: `scripts/validate_postgres_local.py` generates. Nothing else is accepted.
ALLOWED_TEST_DATABASE_NAME = "nba_test_ci"
ALLOWED_TEST_DATABASE_PREFIX = "nba_test_tmp_"

CONNECT_TIMEOUT_SECONDS = 2
CORE_SCHEMA = "core"

_ALEMBIC_INI_PATH = Path(__file__).resolve().parents[2] / "alembic.ini"


def required_mode() -> bool:
    """Whether environment problems must fail rather than skip."""

    return (
        os.getenv(REQUIRE_POSTGRES_INTEGRATION_ENV, "").strip().lower()
        in REQUIRED_MODE_TRUTHY_VALUES
    )


def skip_or_fail(message: str) -> NoReturn:
    """The one place that decides whether an environment problem is fatal.

    Only conditions about the *environment* reach this. An assertion made by a
    test is never converted into a skip.
    """

    if required_mode():
        pytest.fail(message, pytrace=False)
    pytest.skip(message)


def _fail(message: str) -> NoReturn:
    """A configuration error that is dangerous in either mode."""

    pytest.fail(message, pytrace=False)


@pytest.fixture(scope="session")
def current_alembic_heads() -> frozenset[str]:
    """The repository's head revision(s), resolved from the shipped scripts.

    Resolved from a path derived from this file rather than the process working
    directory, and returned as a set because a repository may legitimately carry
    more than one head. No test may hard-code a revision: a whitelist that has
    to be edited whenever a migration lands is a test that fails for the wrong
    reason, which is exactly how this lane broke.
    """

    config = Config(str(_ALEMBIC_INI_PATH))
    script_location = config.get_main_option("script_location") or "alembic"
    config.set_main_option(
        "script_location", str((_ALEMBIC_INI_PATH.parent / script_location).resolve())
    )
    # Keep the ini's relative `prepend_sys_path` entries out of `sys.path`; they
    # would resolve against the working directory this fixture avoids.
    config.set_main_option("prepend_sys_path", "")

    return frozenset(ScriptDirectory.from_config(config).get_heads())


@pytest.fixture(scope="session")
def postgres_engine(current_alembic_heads: frozenset[str]) -> Iterator[Engine]:
    """A validated Engine against an authorized, empty, head-revision database.

    Everything before `create_engine` is a paper exercise on environment
    variables and a parsed URL. That ordering is the safety property: an
    unauthorized or unsafe configuration is rejected without a socket being
    opened.
    """

    _require_test_database_opt_in()
    database_name = _require_approved_database_name()

    engine = create_engine(
        get_settings().database_url,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        pool_pre_ping=True,
    )
    try:
        _require_reachable(engine)
        _require_current_head(engine, current_alembic_heads)
        _require_empty_core(
            engine,
            f"{database_name!r} already holds data, so it is not the disposable "
            f"database this lane is allowed to use",
        )
        yield engine
        _require_empty_core(
            engine,
            "the integration session left rows behind, so some test committed "
            "outside its rolled-back transaction",
        )
    finally:
        engine.dispose()


@pytest.fixture
def postgres_connection(postgres_engine: Engine) -> Iterator[Connection]:
    """A Connection whose work is always rolled back."""

    connection = postgres_engine.connect()
    try:
        # Any read during validation autobegan a transaction on this Connection;
        # end it before opening the explicit one whose rollback is the whole
        # guarantee here.
        connection.rollback()
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
    finally:
        connection.close()


@pytest.fixture
def postgres_session(postgres_connection: Connection) -> Iterator[Session]:
    """A Session that cannot commit the transaction it borrows.

    `join_transaction_mode="create_savepoint"` means a `Session.commit()` by the
    code under test releases a savepoint instead of committing the outer
    transaction. That lets the loader keep its real caller-owned-transaction
    behaviour while the fixture retains ownership of what actually reaches disk.
    """

    session = Session(
        bind=postgres_connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def postgres_api_client(postgres_connection: Connection) -> Iterator[TestClient]:
    """The real app, reading the caller's uncommitted rows.

    Every database route resolves its Session through `get_request_session`, so
    overriding that one dependency covers teams, seasons, and readiness alike.
    The override builds a *fresh* Session per request on the test's outer
    Connection: no Session is shared between the test thread and the worker
    thread FastAPI runs sync routes in, and none outlives its request.

    Requests are made serially by the tests, so the single Connection is never
    used concurrently.
    """

    def override_request_session() -> Iterator[Session]:
        session = Session(
            bind=postgres_connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            session.close()

    app = create_app()
    app.dependency_overrides[get_request_session] = override_request_session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def _require_test_database_opt_in() -> None:
    value = os.getenv(TEST_DATABASE_ENV)
    if value is None or value.strip() != TEST_DATABASE_OPT_IN_VALUE:
        skip_or_fail(
            f"{TEST_DATABASE_ENV} is not set to exactly '1'. These tests write to "
            f"the database named by DATABASE_URL, so they refuse to connect "
            f"without that explicit authorization. Run "
            f"`uv run python scripts/validate_postgres_local.py`, which creates "
            f"and drops a disposable database for you."
        )


def _require_approved_database_name() -> str:
    """Reject an authorized-but-dangerous configuration outright.

    A caller who set the opt-in flag while pointing DATABASE_URL at some other
    database has authorized destruction of the wrong thing. That is a mistake to
    stop, not an environment gap to skip past, so it fails in both modes.
    """

    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "postgresql":
        skip_or_fail(
            f"DATABASE_URL must configure PostgreSQL for this lane, not "
            f"{url.get_backend_name()!r}"
        )

    name = url.database or ""
    if name != ALLOWED_TEST_DATABASE_NAME and not name.startswith(ALLOWED_TEST_DATABASE_PREFIX):
        _fail(
            f"{TEST_DATABASE_ENV} is set but DATABASE_URL names {name!r}, which is "
            f"not a disposable test database. Only {ALLOWED_TEST_DATABASE_NAME!r} "
            f"and names beginning {ALLOWED_TEST_DATABASE_PREFIX!r} may be used."
        )
    return name


def _require_reachable(engine: Engine) -> None:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        skip_or_fail(f"PostgreSQL is unavailable: {exc}")


def _require_current_head(engine: Engine, heads: frozenset[str]) -> None:
    try:
        with engine.connect() as connection:
            applied = frozenset(
                connection.scalars(text("SELECT version_num FROM alembic_version")).all()
            )
    except SQLAlchemyError as exc:
        skip_or_fail(f"PostgreSQL schema is not migrated: {exc}")

    if not applied:
        skip_or_fail("PostgreSQL schema has no Alembic revision")
    if applied != heads:
        skip_or_fail(
            f"PostgreSQL schema is at {sorted(applied)}, not the migration "
            f"head {sorted(heads)}"
        )


def _require_empty_core(engine: Engine, reason: str) -> None:
    """Every mapped `core` table must hold nothing.

    Derived from the mapped metadata rather than a hand-kept list, so a model
    added later is covered without anyone remembering to add it. Serves two
    purposes: before the session it rejects a database that is evidently not
    disposable, and after it detects a test that escaped its rollback.
    """

    populated: list[str] = []
    with engine.connect() as connection:
        for table in _mapped_core_tables():
            count = connection.scalar(select(func.count()).select_from(table)) or 0
            if count:
                populated.append(f"{table.fullname}={count}")

    if populated:
        pytest.fail(f"{reason}: {', '.join(sorted(populated))}", pytrace=False)


def _mapped_core_tables() -> list:
    return [table for table in Base.metadata.sorted_tables if table.schema == CORE_SCHEMA]
