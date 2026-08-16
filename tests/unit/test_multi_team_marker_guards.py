"""Every layer that rejects `TOT` must reject a team-count marker too.

Without these the fourteen enforcement sites are changed but unproven: a `5TM`
value that slipped past the normalizer would be written as a real team, which
is the outcome ADR 0007 forbids.
"""

from __future__ import annotations

import gzip
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

import nba_data.scraping.cache_inventory as cache_inventory
from nba_data.db.models import (
    Player,
    PlayerSeason,
    PlayerTeamSeason,
    Season,
    Team,
    TeamAlias,
    TeamSeason,
)
from nba_data.db.repositories import CoreRepository
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.cache_inventory import (
    _CACHE_TEAM_SEASON_FILE_RE,
    _CachedHtmlMetadata,
    build_cached_html_inventory,
)
from nba_data.scraping.loaders.team_season import TeamSeasonLoadBatch, _validate_before_writes
from nba_data.scraping.loaders.team_season_stats import _route_for_row
from nba_data.scraping.offline_processor import _normalize_team_abbreviation
from nba_data.scraping.offline_stats_backfill import _normalize_team_filter
from nba_data.validation.offline_database import _synthetic_team_code_issues
from nba_data.validation.team_season import validate_normalized_team_season_rows

MARKERS = ("2TM", "3TM", "4TM", "5TM", "6TM", "10TM")

CORE_TABLES = (
    Season.__table__,
    Team.__table__,
    TeamAlias.__table__,
    Player.__table__,
    TeamSeason.__table__,
    PlayerSeason.__table__,
    PlayerTeamSeason.__table__,
)


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:")
    connection = engine.connect()
    connection.exec_driver_sql("ATTACH DATABASE ':memory:' AS core")
    for table in CORE_TABLES:
        table.create(connection)

    session_factory = sessionmaker(bind=connection, autoflush=False, expire_on_commit=False)
    with session_factory() as test_session:
        yield test_session

    connection.close()
    engine.dispose()


@pytest.mark.unit
@pytest.mark.parametrize("marker", MARKERS)
def test_core_writer_refuses_a_marker_as_a_team(session: Session, marker: str) -> None:
    repository = CoreRepository(session)

    with pytest.raises(ValueError, match=marker):
        repository.get_or_create_team(
            basketball_reference_team_id=marker,
            current_abbreviation=marker,
            current_name=marker,
        )


@pytest.mark.unit
@pytest.mark.parametrize("marker", MARKERS)
def test_core_writer_refuses_a_marker_as_a_team_alias(session: Session, marker: str) -> None:
    repository = CoreRepository(session)
    team = repository.get_or_create_team(
        basketball_reference_team_id="DEN",
        current_abbreviation="DEN",
        current_name="Denver Nuggets",
    )

    with pytest.raises(ValueError, match=marker):
        repository.get_or_create_team_alias(
            team=team,
            abbreviation=marker,
            name=marker,
            season_year=2008,
        )


@pytest.mark.unit
@pytest.mark.parametrize("marker", MARKERS)
def test_core_writer_refuses_a_marker_as_a_team_season(session: Session, marker: str) -> None:
    repository = CoreRepository(session)
    team = repository.get_or_create_team(
        basketball_reference_team_id="DEN",
        current_abbreviation="DEN",
        current_name="Denver Nuggets",
    )
    season = repository.get_or_create_season(league="NBA", season_year=2008)

    with pytest.raises(ValueError, match=marker):
        repository.get_or_create_team_season(
            team=team,
            season=season,
            team_abbreviation=marker,
        )


@pytest.mark.unit
def test_core_writer_still_refuses_tot_exactly_as_before(session: Session) -> None:
    repository = CoreRepository(session)

    with pytest.raises(ValueError, match="TOT"):
        repository.get_or_create_team(
            basketball_reference_team_id="TOT",
            current_abbreviation="TOT",
            current_name="Total",
        )


@pytest.mark.unit
def test_core_writer_still_accepts_real_team_codes(session: Session) -> None:
    repository = CoreRepository(session)
    team = repository.get_or_create_team(
        basketball_reference_team_id="DEN",
        current_abbreviation="DEN",
        current_name="Denver Nuggets",
    )
    season = repository.get_or_create_season(league="NBA", season_year=2008)

    assert team.basketball_reference_team_id == "DEN"
    assert (
        repository.get_or_create_team_season(
            team=team, season=season, team_abbreviation="DEN"
        ).team_abbreviation
        == "DEN"
    )


@pytest.mark.unit
@pytest.mark.parametrize(
    ("statement", "parameters"),
    [
        (
            "insert into core.teams (id, basketball_reference_team_id, current_abbreviation, "
            "current_name) values (99, :code, 'DEN', 'Denver Nuggets')",
            {"code": "5TM"},
        ),
        (
            "insert into core.teams (id, basketball_reference_team_id, current_abbreviation, "
            "current_name) values (99, 'DEN', :code, 'Denver Nuggets')",
            {"code": "5TM"},
        ),
        (
            "insert into core.team_aliases (id, team_id, abbreviation, name) "
            "values (99, 1, :code, 'Total')",
            {"code": "5TM"},
        ),
        (
            "insert into core.team_seasons (id, team_id, season_id, team_abbreviation) "
            "values (99, 1, 1, :code)",
            {"code": "5TM"},
        ),
    ],
)
def test_check_constraints_reject_a_marker_written_around_the_repository(
    session: Session, statement: str, parameters: dict[str, str]
) -> None:
    """The database is the last line of defence, so drive it directly."""

    _seed_real_team(session)

    with pytest.raises(IntegrityError):
        session.execute(text(statement), parameters)
        session.flush()


@pytest.mark.unit
@pytest.mark.parametrize("marker", MARKERS)
def test_normalized_team_season_validation_reports_a_marker(marker: str) -> None:
    issues = validate_normalized_team_season_rows(
        [_normalized_row(team_abbreviation=marker)],
        require_stable_player_id=False,
    )

    assert [issue.code for issue in issues] == ["multi_team_marker_not_a_team"]


@pytest.mark.unit
def test_normalized_team_season_validation_keeps_tot_classification_rules() -> None:
    misclassified = validate_normalized_team_season_rows(
        [_normalized_row(team_abbreviation="TOT")],
        require_stable_player_id=False,
    )
    correctly_classified = validate_normalized_team_season_rows(
        [
            _normalized_row(
                team_abbreviation="TOT",
                team_context="aggregate",
                stat_scope="player_season_aggregate",
            )
        ],
        require_stable_player_id=False,
    )

    assert [issue.code for issue in misclassified] == ["tot_not_aggregate"]
    assert correctly_classified == []


@pytest.mark.unit
def test_offline_database_validator_counts_markers_as_synthetic(session: Session) -> None:
    """Phase 4D validates a database that may predate the check constraints.

    The constraints are suspended so the rows can be seeded at all — which is
    itself the state this validator exists to report.
    """

    _seed_real_team(session)
    session.execute(text("PRAGMA ignore_check_constraints = ON"))
    session.execute(
        text(
            "insert into core.teams (id, basketball_reference_team_id, current_abbreviation, "
            "current_name) values (2, '5TM', '5TM', '5TM')"
        )
    )
    session.execute(
        text(
            "insert into core.team_aliases (id, team_id, abbreviation, name) "
            "values (2, 2, '5TM', '5TM')"
        )
    )
    session.execute(
        text(
            "insert into core.team_seasons (id, team_id, season_id, team_abbreviation) "
            "values (2, 2, 1, '5TM')"
        )
    )

    issues = _synthetic_team_code_issues(session)

    assert {issue.code for issue in issues} == {
        "teams_synthetic_code_rows",
        "team_aliases_synthetic_code_rows",
        "team_seasons_synthetic_code_rows",
    }
    assert all(issue.context["count"] == 1 for issue in issues)


@pytest.mark.unit
@pytest.mark.parametrize("marker", MARKERS)
def test_offline_processor_refuses_a_marker_as_a_team_abbreviation(marker: str) -> None:
    # Rejection is the contract; which guard fires first is not. The
    # three-letter shape check already excludes numeric markers here, so the
    # synthetic-code guard behind it is defence in depth.
    with pytest.raises(ValueError):
        _normalize_team_abbreviation(marker)


@pytest.mark.unit
@pytest.mark.parametrize("marker", MARKERS)
def test_cache_inventory_marks_a_marker_source_unsupported(tmp_path, monkeypatch, marker) -> None:
    """The inventory guard is defence in depth.

    A marker cannot reach it through discovery — the cache filename pattern
    admits three letters and nothing else, which
    `test_cache_inventory_filenames_cannot_carry_a_numeric_marker` pins down —
    so the metadata step is replaced to reach the guard itself.
    """

    cache = HtmlCache(tmp_path / "cache")
    cache_path = cache.path_for_url("https://www.basketball-reference.com/teams/BOS/2008.html")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(cache_path, "wt", encoding="utf-8") as file:
        file.write("<!doctype html><html><body>cached</body></html>")

    monkeypatch.setattr(
        cache_inventory,
        "_infer_metadata",
        lambda relative_path: _CachedHtmlMetadata(
            team_abbreviation=marker,
            season_end_year=2008,
            source_url=f"https://www.basketball-reference.com/teams/{marker}/2008.html",
        ),
    )

    inventory = build_cached_html_inventory(cache=cache)

    entry = inventory.entries[0]
    assert entry.status == "unsupported_path"
    assert entry.error_message == f"{marker} is an aggregate marker, not a real team."


@pytest.mark.unit
@pytest.mark.parametrize("marker", MARKERS)
def test_offline_stats_backfill_refuses_a_marker_as_a_team_filter(marker: str) -> None:
    with pytest.raises(ValueError, match="not a real team"):
        _normalize_team_filter(marker)


@pytest.mark.unit
@pytest.mark.parametrize("marker", MARKERS)
def test_team_season_stats_routing_refuses_a_marker_as_a_stint(marker: str) -> None:
    entry = _route_for_row(
        row={"team_abbreviation": marker},
        row_index=0,
        source_table="totals",
        stat_scope="player_team_season",
        aggregate=False,
    )

    assert entry.reason == "invalid_multi_team_marker_routing"


@pytest.mark.unit
@pytest.mark.parametrize("marker", MARKERS)
def test_team_season_loader_refuses_a_marker_row(marker: str) -> None:
    batch = TeamSeasonLoadBatch(
        league="NBA",
        season_year=2008,
        team_abbreviation="DEN",
        team_name="Denver Nuggets",
        rows=[_normalized_row(team_abbreviation=marker)],
    )

    with pytest.raises(ValueError, match=marker):
        _validate_before_writes(batch, "DEN")


@pytest.mark.unit
@pytest.mark.parametrize("marker", MARKERS)
def test_cache_inventory_filenames_cannot_carry_a_numeric_marker(marker: str) -> None:
    filename = f"teams-{marker.lower()}-2008.html-0123456789abcdef.html.gz"

    assert _CACHE_TEAM_SEASON_FILE_RE.fullmatch(filename) is None


def _seed_real_team(session: Session) -> None:
    repository = CoreRepository(session)
    team = repository.get_or_create_team(
        basketball_reference_team_id="DEN",
        current_abbreviation="DEN",
        current_name="Denver Nuggets",
    )
    season = repository.get_or_create_season(league="NBA", season_year=2008)
    repository.get_or_create_team_season(team=team, season=season, team_abbreviation="DEN")
    session.flush()


def _normalized_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "league": "NBA",
        "season_year": 2008,
        "team_abbreviation": "DEN",
        "source_table": "totals",
        "stat_scope": "player_team_season",
        "team_context": "team",
        "player_name": "Bobby Jones",
        "basketball_reference_player_id": "jonesbo02",
    }
    row.update(overrides)
    return row
