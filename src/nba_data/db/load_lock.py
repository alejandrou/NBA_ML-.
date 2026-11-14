"""One load at a time per database (DATABASE_AUDIT_2026-11-10, R-02).

The loaders select and then insert, without `ON CONFLICT`. Two loads running at
once would collide on a unique constraint and one would abort halfway. A
session-level advisory lock, taken before any write and held until the command
ends, makes the second load fail at once with a clear message instead.

The lock belongs to one PostgreSQL backend, so the load writes through that same
backend. A lock held on a side connection would protect nothing once that
connection dropped: the server would release it and a second load could start
while the first kept writing. Here, losing the connection loses the writer too.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from typing import Any

from sqlalchemy import Engine, event, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

# An arbitrary, fixed 64-bit key shared by every load command. Only this
# project's loads take it, so it cannot clash with another application's lock.
LOAD_LOCK_KEY = 7_314_250_118_402_611_001


class LoadInProgressError(RuntimeError):
    """Another load holds the database's load lock."""


class LoadLockLostError(BaseException):
    """The connection holding the load lock was replaced mid-load.

    A `BaseException`, like `KeyboardInterrupt`: the producers record an
    `Exception` raised while loading one page and move on to the next, and a
    lost lock must end the whole load instead.
    """


@contextmanager
def exclusive_load(engine: Engine) -> Iterator[Engine | Connection]:
    """Hold the database's load lock and yield what the load must write through.

    On PostgreSQL that is the Connection holding the lock. It is left idle (not in
    a transaction) when yielded, so it pins no snapshot until the load begins
    work. Every statement it runs is checked to still use the backend that took
    the lock: if the server or a network fault drops it, SQLAlchemy would quietly
    reconnect on the next use, and that statement raises `LoadLockLostError`
    instead of writing without the lock.

    Fails immediately, never waits, when another load holds the lock. PostgreSQL
    releases it if the process dies. Any other database has no concurrent
    writers to guard against: the engine itself is yielded, without a lock.
    """
    if engine.dialect.name != "postgresql":
        yield engine
        return

    with engine.connect() as connection:
        acquired = connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": LOAD_LOCK_KEY}
        )
        connection.commit()
        if not acquired:
            msg = (
                "Another load is already writing this database (advisory lock "
                f"{LOAD_LOCK_KEY} is held). Wait for it to finish, then run this load again."
            )
            raise LoadInProgressError(msg)

        locked_backend = connection.connection.dbapi_connection

        def refuse_a_replaced_backend(conn: Connection, *_args: Any) -> None:
            if conn.connection.dbapi_connection is not locked_backend:
                msg = (
                    "The connection holding the load lock was lost and replaced; "
                    "another load may now hold the lock, so this load stops. "
                    "Pages committed before the loss are kept; run the load again."
                )
                raise LoadLockLostError(msg)

        event.listen(connection, "before_cursor_execute", refuse_a_replaced_backend)
        try:
            yield connection
        finally:
            event.remove(connection, "before_cursor_execute", refuse_a_replaced_backend)
            # Leave nothing the load did not commit, then release. A lost
            # connection has already released the lock (and reading
            # `.connection` would reconnect it); an error here must not hide the
            # load's own outcome.
            with suppress(SQLAlchemyError):
                connection.rollback()
                if (
                    not connection.invalidated
                    and connection.connection.dbapi_connection is locked_backend
                ):
                    connection.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": LOAD_LOCK_KEY}
                    )
                    connection.commit()
