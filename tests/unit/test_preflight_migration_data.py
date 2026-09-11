from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from scripts import preflight_migration_data
from sqlalchemy.sql.elements import TextClause

#: The shape `0008` requires: the three superseded tables, nothing else, no rows.
_CLEAN_RAW_RELATIONS = (
    ("raw_pages", "r"),
    ("scraper_requests", "r"),
    ("scraper_runs", "r"),
)


@dataclass
class FakeDatabase:
    """What a target would answer, described once instead of per statement."""

    null_count: int = 0
    raw_schema_present: bool = True
    relations: tuple[tuple[str, str], ...] = _CLEAN_RAW_RELATIONS
    routines: tuple[tuple[str, str], ...] = ()
    row_counts: dict[str, int] = field(default_factory=dict)


class FakeResult:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows

    def scalar_one(self) -> object:
        return self.rows[0][0]

    def all(self) -> list[tuple[object, ...]]:
        return list(self.rows)


class FakeConnection:
    def __init__(self, database: FakeDatabase) -> None:
        self.database = database
        self.execution_options_seen: dict[str, object] | None = None
        self.statements: list[TextClause] = []

    def __enter__(self) -> FakeConnection:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        return None

    def execution_options(self, **options: object) -> FakeConnection:
        self.execution_options_seen = options
        return self

    def execute(
        self, statement: TextClause, parameters: dict[str, object] | None = None
    ) -> FakeResult:
        self.statements.append(statement)
        return FakeResult(self._rows_for(statement.text))

    def _rows_for(self, sql: str) -> list[tuple[object, ...]]:
        database = self.database
        if sql == preflight_migration_data._COUNT_NULL_TEAM_CODES_SQL:
            return [(database.null_count,)]
        if sql == preflight_migration_data._RAW_SCHEMA_EXISTS_SQL:
            return [(int(database.raw_schema_present),)]
        if sql == preflight_migration_data._RAW_RELATION_INVENTORY_SQL:
            return list(database.relations)
        if sql == preflight_migration_data._RAW_ROUTINE_INVENTORY_SQL:
            return list(database.routines)
        if sql.startswith("SELECT count(*) FROM raw."):
            table = sql.rsplit(".", 1)[1]
            if table not in {name for name, _ in database.relations}:
                raise AssertionError(f"counted a table the catalog did not report: {table!r}")
            return [(database.row_counts.get(table, 0),)]
        raise AssertionError(f"unexpected statement: {sql!r}")


class FakeEngine:
    def __init__(self, database: FakeDatabase) -> None:
        self.connection = FakeConnection(database)
        self.connect_calls = 0
        self.dispose_calls = 0

    def connect(self) -> FakeConnection:
        self.connect_calls += 1
        return self.connection

    def dispose(self) -> None:
        self.dispose_calls += 1


def _install_fake_engine(
    monkeypatch: pytest.MonkeyPatch, database: FakeDatabase
) -> tuple[FakeEngine, list[tuple[str, dict[str, object]]]]:
    engine = FakeEngine(database)
    calls: list[tuple[str, dict[str, object]]] = []

    def fake_create_engine(url: str, **kwargs: object) -> FakeEngine:
        calls.append((url, kwargs))
        return engine

    monkeypatch.setattr(preflight_migration_data, "create_engine", fake_create_engine)
    return engine, calls


def _run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    database: FakeDatabase,
) -> tuple[int, str, str, FakeEngine]:
    engine, _ = _install_fake_engine(monkeypatch, database)
    exit_code = preflight_migration_data.main(
        ["--database-url", "postgresql+psycopg://owner:secret@example.test:5432/nba"]
    )
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err, engine


@pytest.mark.unit
@pytest.mark.parametrize(
    ("null_count", "expected_exit_code"),
    [(0, 0), (2, 1)],
    ids=["zero-null-rows", "null-rows"],
)
def test_preflight_reports_the_0007_count_over_a_read_only_connection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    null_count: int,
    expected_exit_code: int,
) -> None:
    engine, calls = _install_fake_engine(monkeypatch, FakeDatabase(null_count=null_count))
    database_url = "postgresql+psycopg://owner:secret@example.test:5432/nba"

    assert preflight_migration_data.main(["--database-url", database_url]) == expected_exit_code

    # A target that never answers must time out and report, not hang forever.
    assert calls == [
        (
            database_url,
            {
                "connect_args": {
                    "connect_timeout": preflight_migration_data.CONNECT_TIMEOUT_SECONDS
                }
            },
        )
    ]
    assert engine.connect_calls == 1
    assert engine.dispose_calls == 1
    assert engine.connection.execution_options_seen == {"postgresql_readonly": True}

    executed = [statement.text for statement in engine.connection.statements]
    assert executed.count(preflight_migration_data._COUNT_NULL_TEAM_CODES_SQL) == 1

    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert f"NULL count: {null_count}" in captured.out
    assert preflight_migration_data._TARGET_COLUMN in output
    assert "secret" not in output
    if null_count:
        assert "must not be applied" in captured.err
        assert "Remediation is a separate decision for the user." in captured.err
    else:
        assert "Preflight passed" in captured.out


@pytest.mark.unit
def test_the_preflight_only_ever_reads(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Not one statement the command sends may be capable of changing a target.

    The read-only transaction is the enforced guarantee and is proven against a
    real server in the integration lane. This is the cheap structural check that
    catches a repair or a fix-up being added to a command an owner points at a
    database they are about to migrate.
    """

    _, _, _, engine = _run(monkeypatch, capsys, FakeDatabase())

    for statement in engine.connection.statements:
        assert statement.text.strip().upper().startswith("SELECT"), statement.text


@pytest.mark.unit
def test_a_clean_raw_schema_passes_the_0008_precondition(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code, out, err, _ = _run(monkeypatch, capsys, FakeDatabase())

    assert exit_code == 0, err
    assert f"Preflight passed for {preflight_migration_data._MIGRATION_0008}" in out
    for table in preflight_migration_data._EXPECTED_RAW_TABLES:
        assert f"raw.{table} row count: 0" in out
    assert err == ""


@pytest.mark.unit
def test_an_absent_raw_schema_passes_without_counting_anything(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The state `nba` is in once 0008 has been applied is a pass, not a failure."""

    exit_code, out, err, engine = _run(
        monkeypatch,
        capsys,
        FakeDatabase(raw_schema_present=False, relations=()),
    )

    assert exit_code == 0, err
    assert "schema raw is absent" in out
    assert f"Preflight passed for {preflight_migration_data._MIGRATION_0008}" in out

    executed = [statement.text for statement in engine.connection.statements]
    assert preflight_migration_data._RAW_RELATION_INVENTORY_SQL not in executed
    assert not [sql for sql in executed if sql.startswith("SELECT count(*) FROM raw.")]


@pytest.mark.unit
def test_a_populated_raw_table_blocks_0008_and_names_its_row_count(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The blocker an owner acts on is the one that says which rows are at risk."""

    exit_code, out, err, _ = _run(
        monkeypatch, capsys, FakeDatabase(row_counts={"raw_pages": 12})
    )

    assert exit_code == 1
    assert "raw.raw_pages row count: 12" in out
    assert "raw.raw_pages has 12 row(s)" in err
    assert f"Migration {preflight_migration_data._MIGRATION_0008} must not be applied." in err
    assert "Remediation is a separate decision for the user." in err
    # A row count is not an unknown object, and must not be reported as one.
    assert "unrecognized" not in err


@pytest.mark.unit
@pytest.mark.parametrize(
    ("database", "expected_fragment"),
    [
        (
            FakeDatabase(relations=(*_CLEAN_RAW_RELATIONS, ("_unexpected_guard", "r"))),
            "unrecognized table 'raw._unexpected_guard'",
        ),
        (
            FakeDatabase(relations=(*_CLEAN_RAW_RELATIONS, ("leftover_view", "v"))),
            "unrecognized view 'raw.leftover_view'",
        ),
        (
            FakeDatabase(relations=(*_CLEAN_RAW_RELATIONS, ("loose_seq", "S"))),
            "unrecognized sequence 'raw.loose_seq'",
        ),
        (
            FakeDatabase(routines=(("stale_fn", "f"),)),
            "unrecognized function 'raw.stale_fn'",
        ),
    ],
    ids=["table", "view", "sequence", "routine"],
)
def test_an_unrecognized_raw_object_blocks_0008(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    database: FakeDatabase,
    expected_fragment: str,
) -> None:
    """`DROP SCHEMA raw` carries no CASCADE, so anything unexpected aborts it."""

    exit_code, _, err, _ = _run(monkeypatch, capsys, database)

    assert exit_code == 1
    assert expected_fragment in err
    assert "without CASCADE" in err
    # Every expected table is still empty here, so nothing may claim otherwise.
    assert "row(s);" not in err


@pytest.mark.unit
def test_a_partially_present_raw_schema_blocks_0008(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """0008 drops all three tables by name and aborts on the first one missing."""

    exit_code, _, err, _ = _run(
        monkeypatch,
        capsys,
        FakeDatabase(relations=(("raw_pages", "r"),)),
    )

    assert exit_code == 1
    assert "raw.scraper_runs is missing" in err
    assert "raw.scraper_requests is missing" in err


@pytest.mark.unit
def test_a_blocked_0007_still_reports_the_0008_verdict(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """One failing precondition must not hide the state of the other."""

    exit_code, out, err, _ = _run(
        monkeypatch,
        capsys,
        FakeDatabase(null_count=3, row_counts={"scraper_runs": 5}),
    )

    assert exit_code == 1
    assert f"3 row(s) have NULL {preflight_migration_data._TARGET_COLUMN}" in err
    assert "raw.scraper_runs has 5 row(s)" in err
    assert f"Migration {preflight_migration_data._MIGRATION_0007} must not be applied." in err
    assert f"Migration {preflight_migration_data._MIGRATION_0008} must not be applied." in err
    assert "Preflight passed" not in out


@pytest.mark.unit
@pytest.mark.parametrize(
    "argv",
    [[], ["--database-url", ""], ["--database-url", "   "]],
    ids=["missing", "empty", "blank"],
)
def test_preflight_refuses_to_run_without_a_named_target(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
) -> None:
    """An unnamed target is a usage error, not a database to go and inspect.

    The blank cases matter because `--database-url "$DATABASE_URL"` sends an
    empty string whenever that variable is unset, which `required=True` accepts.
    """

    monkeypatch.setattr(preflight_migration_data, "create_engine", _fail_if_called)

    with pytest.raises(SystemExit) as error:
        preflight_migration_data.main(argv)

    assert error.value.code == 2
    assert "--database-url" in capsys.readouterr().err


@pytest.mark.unit
@pytest.mark.parametrize(
    ("database_url", "expected_message"),
    [
        ("sqlite:///./local.db", "not 'sqlite'"),
        ("not a url at all", "not a database URL SQLAlchemy can parse"),
    ],
    ids=["wrong-backend", "unparseable"],
)
def test_preflight_rejects_a_target_it_could_not_assess(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    database_url: str,
    expected_message: str,
) -> None:
    """Named as a usage error before connecting, rather than failed after.

    The checks below read PostgreSQL schemas and catalogs through a
    PostgreSQL-only read-only option, so any other backend is a mistake about
    which database is being assessed — the one class of mistake this command
    exists to prevent.
    """

    monkeypatch.setattr(preflight_migration_data, "create_engine", _fail_if_called)

    with pytest.raises(SystemExit) as error:
        preflight_migration_data.main(["--database-url", database_url])

    assert error.value.code == 2
    assert expected_message in capsys.readouterr().err


def _fail_if_called(url: str, **kwargs: object) -> FakeEngine:
    raise AssertionError(f"create_engine should not run: {url}")
