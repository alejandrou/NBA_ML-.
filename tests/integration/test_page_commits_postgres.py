"""Committed pages really persist, and a load cannot outlive its lock, on PostgreSQL.

R-03 (DATABASE_AUDIT_2026-11-10): each stats producer commits page by page, so a
run stopped on page two keeps page one, visibly to every other connection, and a
rerun completes the load without duplicating it.

R-02: the load writes through the connection that holds the advisory lock. When
that connection is lost, the server releases the lock, so the load must not go
on writing through a fresh connection.

These tests commit, which the rest of this lane never does: `committed_database`
empties `core` and `stats` again afterwards, so the session-wide check that the
lane leaves no rows behind still holds.
"""

from __future__ import annotations

import gzip
from collections.abc import Callable, Iterator
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

import nba_data.scraping.offline_player_postseason_stats_backfill as postseason_module
import nba_data.scraping.offline_player_stats_backfill as regular_module
import nba_data.scraping.offline_stats_backfill as team_module
from nba_data.api.services import readiness
from nba_data.db.load_lock import LoadLockLostError, exclusive_load
from nba_data.db.models import (
    PlayerPostseasonTotals,
    PlayerSeasonTotals,
    PlayerTeamPostseasonTotals,
    PlayerTeamSeasonTotals,
)
from nba_data.db.repositories import CoreRepository
from nba_data.db.session import create_session_factory
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.cache_inventory import CachedHtmlInventory, CachedHtmlInventoryEntry
from nba_data.scraping.offline_processor import (
    OfflineTeamSeasonEntryResult,
    OfflineTeamSeasonProcessingReport,
    OfflineTeamSeasonSourceContext,
)

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "html"
TEAM_PAGES = (("ATL", "youngtr01", "Trae Young"), ("BOS", "tatumja01", "Jayson Tatum"))
REGULAR_PLAYERS = (("aaaaaa01", "Page One"), ("bbbbbb01", "Page Two"))
POSTSEASON_PLAYERS = (
    ("brownja02", "Jaylen Brown", 2024, "BOS", "player_page_brown_postseason.html"),
    ("hardeja01", "James Harden", 2021, "BRK", "player_page_harden_postseason.html"),
)


@pytest.fixture
def committed_database(postgres_engine: Engine) -> Iterator[Engine]:
    """The disposable database, emptied of whatever the test committed."""

    try:
        yield postgres_engine
    finally:
        with postgres_engine.begin() as connection:
            tables = connection.scalars(
                text(
                    "SELECT format('%I.%I', schemaname, tablename) FROM pg_catalog.pg_tables "
                    "WHERE schemaname IN ('core', 'stats') ORDER BY 1"
                )
            ).all()
            connection.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))


def _seed(engine: Engine, seed: Callable[[CoreRepository], None]) -> None:
    with Session(engine) as session:
        seed(CoreRepository(session))
        session.commit()


def _count(engine: Engine, model: type) -> int:
    """Counted on a connection of its own: only committed rows are visible."""
    with engine.connect() as observer:
        return int(observer.scalar(select(func.count()).select_from(model)) or 0)


def _stop_on_the_second_page(
    monkeypatch: pytest.MonkeyPatch, module: ModuleType, attribute: str
) -> Callable[[], None]:
    """Make the second page's load raise KeyboardInterrupt; return the undo."""
    real = getattr(module, attribute)
    calls = 0

    def interrupting(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return real(*args, **kwargs)

    monkeypatch.setattr(module, attribute, interrupting)
    return lambda: monkeypatch.setattr(module, attribute, real)


def _run(engine: Engine, produce: Callable[[Session], object]) -> object:
    """As the CLI does: through the locked connection, committing page by page."""
    with exclusive_load(engine) as bind, create_session_factory(bind)() as session:
        return produce(session)


def _write_gzip(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(html)


def _player_url(player_id: str) -> str:
    return f"https://www.basketball-reference.com/players/{player_id[0]}/{player_id}.html"


# --- team-season pages (backfill stats) -------------------------------------


def _team_inventory(cache: HtmlCache) -> CachedHtmlInventory:
    entries = tuple(
        CachedHtmlInventoryEntry(
            cache_path=str(cache.path_for_url(_team_url(team))),
            status="valid",
            source_url=_team_url(team),
            is_basketball_reference=True,
            team_abbreviation=team,
            season_year=2024,
            season_end_year=2024,
            page_type="team_season",
        )
        for team, _player_id, _name in TEAM_PAGES
    )
    return CachedHtmlInventory(
        cache_root=str(cache.root_dir),
        total_discovered_files=len(entries),
        valid_candidates=len(entries),
        invalid_or_unreadable_files=0,
        duplicate_candidates=0,
        missing_metadata=0,
        unsupported_paths=0,
        entries=entries,
    )


def _team_url(team: str) -> str:
    return f"https://www.basketball-reference.com/teams/{team}/2024.html"


def _team_processing(sources: object, **_kwargs: object) -> OfflineTeamSeasonProcessingReport:
    entries = tuple(
        OfflineTeamSeasonEntryResult(
            source=OfflineTeamSeasonSourceContext(
                source_type="path",
                team_abbreviation=team,
                season_year=2024,
                url=_team_url(team),
                # None: the backfill falls back to the inventory path under the root.
                cache_path=None,
            ),
            status="validated",
            parsed_row_count=1,
            normalized_rows=(
                {
                    "league": "NBA",
                    "season_year": 2024,
                    "team_abbreviation": team,
                    "team_context": "team",
                    "source_table": "totals",
                    "stat_scope": "player_team_season",
                    "player_name": name,
                    "basketball_reference_player_id": player_id,
                    "stable_player_key": player_id,
                    "identifier_status": "present",
                    "values": {"games": 70, "pts": 1800},
                },
            ),
        )
        for team, player_id, name in TEAM_PAGES
    )
    return OfflineTeamSeasonProcessingReport(
        total_inputs=len(entries),
        validated_entries=len(entries),
        failed_entries=0,
        validated_row_count=len(entries),
        entries=entries,
    )


def _seed_team_pages(core: CoreRepository) -> None:
    season = core.get_or_create_season(league="NBA", season_year=2024)
    for team_code, player_id, name in TEAM_PAGES:
        team = core.get_or_create_team(
            basketball_reference_team_id=team_code,
            current_abbreviation=team_code,
            current_name=team_code,
        )
        core.get_or_create_team_alias(
            team=team, abbreviation=team_code, name=team_code, season_year=2024
        )
        team_season = core.get_or_create_team_season(
            team=team, season=season, team_abbreviation=team_code
        )
        player = core.get_or_create_player(basketball_reference_player_id=player_id, full_name=name)
        player_season = core.get_or_create_player_season(player=player, season=season)
        core.get_or_create_player_team_season(player_season=player_season, team_season=team_season)


def test_team_pages_committed_before_an_interruption_persist_and_a_rerun_completes(
    committed_database: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = committed_database
    _seed(engine, _seed_team_pages)
    cache = HtmlCache(tmp_path / "cache")
    monkeypatch.setattr(
        team_module, "build_cached_html_inventory", lambda **_: _team_inventory(cache)
    )
    monkeypatch.setattr(team_module, "process_offline_team_season_sources", _team_processing)
    restore = _stop_on_the_second_page(monkeypatch, team_module, "load_team_season_stats")

    def produce(session: Session) -> object:
        return team_module.run_offline_stats_backfill(session, cache=cache, commit_each_page=True)

    with pytest.raises(KeyboardInterrupt):
        _run(engine, produce)
    assert _count(engine, PlayerTeamSeasonTotals) == 1

    restore()
    _run(engine, produce)
    assert _count(engine, PlayerTeamSeasonTotals) == 2


# --- player pages, regular season (backfill player-stats) --------------------


def _regular_season_page() -> str:
    return """
    <html><body><table id="totals_stats">
      <thead><tr>
        <th data-stat="year_id">Season</th><th data-stat="team_name_abbr">Tm</th>
        <th data-stat="comp_name_abbr">Lg</th><th data-stat="games">G</th>
        <th data-stat="pts">PTS</th>
      </tr></thead>
      <tbody><tr>
        <th data-stat="year_id">2020-21</th><td data-stat="team_name_abbr">BOS</td>
        <td data-stat="comp_name_abbr">NBA</td><td data-stat="games">44</td>
        <td data-stat="pts">1083</td>
      </tr></tbody>
    </table></body></html>
    """


def _seed_regular_players(core: CoreRepository) -> None:
    season = core.get_or_create_season(league="NBA", season_year=2021)
    for player_id, name in REGULAR_PLAYERS:
        player = core.get_or_create_player(basketball_reference_player_id=player_id, full_name=name)
        core.get_or_create_player_season(player=player, season=season)


def test_regular_season_player_pages_persist_page_by_page(
    committed_database: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = committed_database
    _seed(engine, _seed_regular_players)
    cache = HtmlCache(tmp_path / "cache")
    for player_id, _name in REGULAR_PLAYERS:
        _write_gzip(cache.path_for_url(_player_url(player_id)), _regular_season_page())
    restore = _stop_on_the_second_page(monkeypatch, regular_module, "load_player_page_stats")

    def produce(session: Session) -> object:
        return regular_module.run_offline_player_stats_backfill(
            session, cache=cache, commit_each_page=True
        )

    with pytest.raises(KeyboardInterrupt):
        _run(engine, produce)
    assert _count(engine, PlayerSeasonTotals) == 1

    restore()
    _run(engine, produce)
    assert _count(engine, PlayerSeasonTotals) == 2


# --- player pages, postseason (backfill player-postseason-stats) -------------


def _seed_postseason_players(core: CoreRepository) -> None:
    for player_id, name, season_year, team_code, _fixture in POSTSEASON_PLAYERS:
        season = core.get_or_create_season(league="NBA", season_year=season_year)
        team = core.get_or_create_team(
            basketball_reference_team_id=team_code,
            current_abbreviation=team_code,
            current_name=team_code,
        )
        core.get_or_create_team_alias(
            team=team, abbreviation=team_code, name=team_code, season_year=season_year
        )
        team_season = core.get_or_create_team_season(
            team=team, season=season, team_abbreviation=team_code
        )
        player = core.get_or_create_player(basketball_reference_player_id=player_id, full_name=name)
        player_season = core.get_or_create_player_season(player=player, season=season)
        core.get_or_create_player_team_season(player_season=player_season, team_season=team_season)


def test_postseason_player_pages_persist_page_by_page(
    committed_database: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = committed_database
    _seed(engine, _seed_postseason_players)
    cache = HtmlCache(tmp_path / "cache")
    for player_id, _name, _season, _team, fixture in POSTSEASON_PLAYERS:
        _write_gzip(
            cache.path_for_url(_player_url(player_id)),
            (FIXTURES / fixture).read_text(encoding="utf-8"),
        )
    restore = _stop_on_the_second_page(monkeypatch, postseason_module, "load_player_page_stats")

    def produce(session: Session) -> object:
        return postseason_module.run_offline_player_postseason_stats_backfill(
            session, cache=cache, commit_each_page=True
        )

    with pytest.raises(KeyboardInterrupt):
        _run(engine, produce)
    assert _count(engine, PlayerPostseasonTotals) == 1
    assert _count(engine, PlayerTeamPostseasonTotals) == 1

    restore()
    _run(engine, produce)
    assert _count(engine, PlayerPostseasonTotals) == 2
    assert _count(engine, PlayerTeamPostseasonTotals) == 2


# --- the lock and its connection ---------------------------------------------


def test_a_load_whose_locked_connection_is_lost_cannot_write_unlocked(
    committed_database: Engine,
) -> None:
    engine = committed_database
    with exclusive_load(engine) as bind, Session(bind=bind) as session:
        backend = session.scalar(text("SELECT pg_backend_pid()"))
        session.commit()
        with engine.connect() as admin:
            assert admin.scalar(text("SELECT pg_terminate_backend(:pid, 5000)"), {"pid": backend})

        # The server released the lock with the backend: another load may start.
        with exclusive_load(engine):
            pass

        with pytest.raises(OperationalError):
            session.execute(text("SELECT 1"))
        session.rollback()
        with pytest.raises(LoadLockLostError, match="lost and replaced"):
            session.execute(
                text(
                    "INSERT INTO core.seasons (league, season_year, label) "
                    "VALUES ('NBA', 2099, '2099')"
                )
            )
        session.rollback()

    with engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM core.seasons")) == 0


# --- readiness and the name collation ----------------------------------------


def test_readiness_finds_the_name_collation_and_misses_an_absent_one(
    postgres_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    with Session(postgres_engine) as session:
        assert readiness._has_name_collation(session)
        monkeypatch.setattr(readiness, "NAME_COLLATION", "no-such-collation-x-icu")
        assert not readiness._has_name_collation(session)
