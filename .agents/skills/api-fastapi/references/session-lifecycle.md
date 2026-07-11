# API reference: session lifecycle

The Engine and `sessionmaker` are long-lived resources owned by one app instance. Lifespan stores the factory on `app.state`; a dependency opens one Session per request and reliably closes it. It never commits. Dispose the Engine during shutdown. Do not create an Engine at import time, per request, or through a global Session, and never share a Session between requests.

The current `get_session()` is not directly suitable for API use because it creates an Engine on every call. Future API work may reuse `create_db_engine()` and `create_session_factory()` once per app instead, without adding async database access. The implementation belongs in F5-002 or the task that introduces DB access.

```python
def create_app() -> FastAPI:
    engine = create_db_engine()
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.session_factory = session_factory
        try:
            yield
        finally:
            engine.dispose()
```

```python
def get_request_session(request: Request) -> Iterator[Session]:
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        yield session
```

Dependency overrides must permit an isolated test Session or fake repository.
