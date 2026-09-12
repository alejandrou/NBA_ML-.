# API reference: session lifecycle

The Engine and `sessionmaker` are long-lived resources owned by one app instance. Lifespan stores the factory on `app.state`; a dependency opens one Session per request and reliably closes it. It never commits. Dispose the Engine during shutdown. Do not create an Engine at import time, per request, or through a global Session, and never share a Session between requests.

`get_session()` is not suitable for API use because it creates an Engine on every call. The API's lifespan in `src/nba_data/api/app.py` instead calls `create_db_engine()` and `create_session_factory()` once per app, without async database access.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = create_db_engine()
    app.state.session_factory = create_session_factory(engine)
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
