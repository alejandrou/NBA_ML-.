"""Overrideable API dependencies live here as read-only resources are added."""

from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker


def get_request_session(request: Request) -> Generator[Session, None, None]:
    """Provide one app-owned-factory Session and close it after the request."""
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    with session_factory() as session:
        yield session
