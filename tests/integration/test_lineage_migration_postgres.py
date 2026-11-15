"""Revision 0013 on populated data: rewrite, refusal, and a round trip.

`scripts/validate_postgres_local.py` round-trips the head revision on empty
tables and compares catalogs; it cannot see a migration that loses or corrupts
data. These tests build their own scratch database next to the lane's
disposable one (same server, `nba_test_tmp_` prefix, always dropped), migrate it
to `0012`, insert rows in both legacy `cache_path` formats, and drive `0013` up,
down, and up again through the real `alembic` command.

They never touch the lane's database, so its empty-database guarantee holds.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nba_data.db.repositories import CoreRepository
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.game_pilot_manifest import box_score_url
from nba_data.scraping.loaders.games import GameLineage, GameLoadResult, load_game
from nba_data.scraping.offline_games_backfill import DEFAULT_GAMES_PARSER_VERSION
from nba_data.scraping.parsers.box_score import parse_box_score_page
from nba_data.scraping.parsers.league_schedule import ScheduleGame

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "html"
BEFORE = "0012_ml_predictions"
TARGET = "0013_portable_lineage_checks"
STAMP = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

WINDOWS_PATH = (
    "C:\\Users\\someone\\Desktop\\repo\\data\\raw\\html\\basketball-reference\\"
    "players-a-abdulma02.html-82dd3fd413cd9608.html.gz"
)
WINDOWS_KEY = "basketball-reference/players-a-abdulma02.html-82dd3fd413cd9608.html.gz"
RELATIVE_PATH = (
    "data\\raw\\html\\basketball-reference\\boxscores-201410280nop.html-3ab33cd3ff459e0f.html.gz"
)
RELATIVE_KEY = "basketball-reference/boxscores-201410280nop.html-3ab33cd3ff459e0f.html.gz"
UNREDUCIBLE_PATH = "D:\\elsewhere\\players-a-x.html.gz"


@pytest.fixture
def scratch_url(postgres_engine: Engine) -> Iterator[URL]:
    """A brand-new database on the lane's server, at revision 0012, dropped after."""

    lane_url = postgres_engine.url
    name = f"nba_test_tmp_{uuid4().hex[:16]}"
    admin = create_engine(lane_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    url = lane_url.set(database=name)
    try:
        _alembic(url, "upgrade", BEFORE)
        yield url
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def _alembic(url: URL, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["DATABASE_URL"] = url.render_as_string(hide_password=False)
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_ok(url: URL, *args: str) -> None:
    result = _alembic(url, *args)
    assert result.returncode == 0, result.stderr


_SEED_SQL = """
                    INSERT INTO core.seasons (id, season_year, league) VALUES (1, 2015, 'NBA');
                    INSERT INTO core.teams (id, basketball_reference_team_id, current_name)
                        VALUES (1, 'NOP', 'New Orleans Pelicans'), (2, 'ORL', 'Orlando Magic');
                    INSERT INTO core.team_seasons (id, team_id, season_id, team_abbreviation)
                        VALUES (1, 1, 1, 'NOP'), (2, 2, 1, 'ORL');
                    INSERT INTO core.players (id, basketball_reference_player_id, full_name)
                        VALUES (1, :player_id, 'Test Player');
                    INSERT INTO core.player_seasons (id, player_id, season_id) VALUES (1, 1, 1);
                    INSERT INTO core.player_team_seasons (id, player_season_id, team_season_id)
                        VALUES (1, 1, 1);
                    INSERT INTO stats.player_season_totals
                        (player_season_id, g, gs, fg, fga, efg_pct,
                         source_url, cache_path, parser_version, created_at, updated_at)
                        VALUES (1, 10, :gs, 5, 10, 1.5,
                                'https://www.basketball-reference.com/players/a/abdulma02.html',
                                :wide_path, 'v4', :stamp, :stamp);
                    INSERT INTO stats.player_team_season_roster
                        (player_team_season_id, source_url, cache_path, parser_version,
                         created_at, updated_at)
                        VALUES (1, 'https://www.basketball-reference.com/teams/NOP/2015.html',
                                :wide_path, 'v4', :stamp, :stamp);
                    INSERT INTO core.games
                        (id, basketball_reference_game_id, season_id, home_team_season_id,
                         away_team_season_id, game_date, game_type, status)
                        VALUES (1, '201410280NOP', 1, 1, 2, '2014-10-28', 'regular_season',
                                'final');
                    INSERT INTO stats.team_game_totals
                        (game_id, team_season_id, is_home, seconds_played, pts,
                         source_url, cache_path, parser_version, created_at, updated_at)
                        VALUES (1, 1, true, 14400, 101,
                                'https://www.basketball-reference.com/boxscores/201410280NOP.html',
                                :game_path, 'v1', :stamp, :stamp);
                    INSERT INTO stats.player_game_totals
                        (game_id, player_id, team_season_id, starter, participation,
                         seconds_played, source_url, cache_path, parser_version,
                         created_at, updated_at)
                        VALUES (1, 1, 1, true, 'played', 1800,
                                'https://www.basketball-reference.com/boxscores/201410280NOP.html',
                                :game_path, 'v1', :stamp, :stamp);
"""


def _seed(url: URL, *, wide_path: str, game_path: str, player_id: str | None, gs: int) -> None:
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            params = {
                "wide_path": wide_path,
                "game_path": game_path,
                "player_id": player_id,
                "gs": gs,
                "stamp": STAMP,
            }
            for statement in _SEED_SQL.split(";"):
                if statement.strip():
                    connection.execute(text(statement), params)
    finally:
        engine.dispose()


def _lineage(url: URL) -> dict[str, tuple[str, datetime, datetime]]:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return {
                table: tuple(
                    connection.execute(
                        text(f"SELECT cache_path, created_at, updated_at FROM stats.{table}")
                    ).one()
                )
                for table in (
                    "player_season_totals",
                    "player_team_season_roster",
                    "team_game_totals",
                    "player_game_totals",
                )
            }
    finally:
        engine.dispose()


def _scalar(url: URL, sql: str) -> object:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return connection.execute(text(sql)).scalar_one()
    finally:
        engine.dispose()


def _new_check_count(url: URL) -> object:
    return _scalar(
        url,
        "SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid = c.connamespace "
        "WHERE n.nspname = 'stats' AND c.contype = 'c' AND (c.conname LIKE '%\\_cache\\_path\\_key' "
        "OR c.conname ~ '^ck_stats_player_(team_)?(season|postseason)_totals_"
        "(non_negative|gs_le_g|makes_le_attempts|pct_range)$')",
    )


def _player_id_nullable(url: URL) -> object:
    return _scalar(
        url,
        "SELECT is_nullable FROM information_schema.columns WHERE table_schema = 'core' "
        "AND table_name = 'players' AND column_name = 'basketball_reference_player_id'",
    )


@pytest.mark.integration
def test_0013_rewrites_both_legacy_formats_and_round_trips(scratch_url: URL) -> None:
    _seed(scratch_url, wide_path=WINDOWS_PATH, game_path=RELATIVE_PATH, player_id="abdulma02", gs=4)

    _run_ok(scratch_url, "upgrade", TARGET)

    upgraded = _lineage(scratch_url)
    assert upgraded["player_season_totals"] == (WINDOWS_KEY, STAMP, STAMP)
    assert upgraded["player_team_season_roster"] == (WINDOWS_KEY, STAMP, STAMP)
    assert upgraded["team_game_totals"] == (RELATIVE_KEY, STAMP, STAMP)
    assert upgraded["player_game_totals"] == (RELATIVE_KEY, STAMP, STAMP)
    assert _new_check_count(scratch_url) == 35 + 4 * 4
    # NOT NULL on the player id is left to a shared card; 0013 must not touch it.
    assert _player_id_nullable(scratch_url) == "YES"

    _run_ok(scratch_url, "downgrade", BEFORE)

    # The schema is restored; the original machine-specific paths are not.
    assert _lineage(scratch_url) == upgraded
    assert _new_check_count(scratch_url) == 0
    assert _player_id_nullable(scratch_url) == "YES"

    _run_ok(scratch_url, "upgrade", TARGET)

    assert _lineage(scratch_url) == upgraded
    assert _new_check_count(scratch_url) == 35 + 4 * 4


@pytest.mark.integration
def test_0013_refuses_and_changes_nothing_when_data_violates_it(scratch_url: URL) -> None:
    _seed(
        scratch_url, wide_path=UNREDUCIBLE_PATH, game_path=RELATIVE_PATH, player_id="abdulma02", gs=11
    )
    before = _lineage(scratch_url)

    result = _alembic(scratch_url, "upgrade", TARGET)

    assert result.returncode != 0
    # The raised message, not the echoed SQL, which names every table.
    message = next(
        line for line in result.stderr.splitlines() if "Refusing to apply 0013:" in line
    )
    assert "stats.player_season_totals: cache_path not reducible to a cache key: 1" in message
    assert "stats.player_team_season_roster: cache_path not reducible" in message
    assert "violates ck_stats_player_season_totals_gs_le_g: 1" in message
    # Valid rows are not listed: the box-score paths are reducible.
    assert "stats.player_game_totals" not in message
    assert _lineage(scratch_url) == before
    assert _scalar(scratch_url, "SELECT version_num FROM alembic_version") == BEFORE
    assert _new_check_count(scratch_url) == 0
    assert _player_id_nullable(scratch_url) == "YES"


@pytest.mark.integration
def test_0013_check_rejects_a_machine_path_written_after_upgrade(scratch_url: URL) -> None:
    _seed(scratch_url, wide_path=WINDOWS_PATH, game_path=RELATIVE_PATH, player_id="abdulma02", gs=4)
    _run_ok(scratch_url, "upgrade", TARGET)

    engine = create_engine(scratch_url)
    try:
        for bad in (WINDOWS_PATH, "/abs/x.html.gz", "../x.html.gz", "a//b.html.gz", "a/./b.html.gz"):
            with (
                pytest.raises(IntegrityError, match="ck_stats_player_season_totals_cache_path_key"),
                engine.begin() as connection,
            ):
                connection.execute(
                    text("UPDATE stats.player_season_totals SET cache_path = :bad"),
                    {"bad": bad},
                )
        with (
            pytest.raises(IntegrityError, match="ck_stats_player_season_totals_pct_range"),
            engine.begin() as connection,
        ):
            connection.execute(text("UPDATE stats.player_season_totals SET efg_pct = 1.51"))
    finally:
        engine.dispose()


BUBBLE_SEASON = 2020
BUBBLE = ScheduleGame(
    game_date=date(2020, 8, 17),
    visitor_code="UTA",
    visitor_name="Utah Jazz",
    home_code="DEN",
    home_name="Denver Nuggets",
    game_id="202008170DEN",
    visitor_points=125,
    home_points=135,
    overtime_periods=1,
    start_time="1:30p",
    arena="HP Field House",
)
BUBBLE_URL = box_score_url("202008170DEN")
# The key the games loader stores for this URL today, from any cache root.
BUBBLE_KEY = HtmlCache("any-root").cache_key_for_url(BUBBLE_URL)


def _load_bubble(session: Session) -> GameLoadResult:
    html = (FIXTURES / "box_score_202008170DEN_trimmed.html").read_text(encoding="utf-8")
    return load_game(
        session,
        BUBBLE,
        parse_box_score_page(html),
        GameLineage(BUBBLE_URL, BUBBLE_KEY, DEFAULT_GAMES_PARSER_VERSION),
        season_end_year=BUBBLE_SEASON,
    )


def _game_rows(url: URL) -> dict[str, list[tuple[object, ...]]]:
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            return {
                table: [
                    tuple(row)
                    for row in connection.execute(
                        text(f"SELECT id, cache_path, updated_at FROM stats.{table} ORDER BY id")
                    )
                ]
                for table in ("team_game_totals", "player_game_totals")
            }
    finally:
        engine.dispose()


@pytest.mark.integration
def test_a_cached_game_reloads_unchanged_after_0013(scratch_url: URL) -> None:
    """The acceptance criterion: legacy rows, upgrade, reload the same file -> no writes.

    The loader compares `cache_path` like any other column, so "unchanged" holds only
    if the migration stored exactly the key the loader computes. Both legacy shapes
    are covered: an absolute Windows path, and a forward-slash path under the cache
    root that already matches the key grammar but is not a key.
    """

    engine = create_engine(scratch_url)
    try:
        with Session(engine) as session:
            core = CoreRepository(session)
            season = core.get_or_create_season(league="NBA", season_year=BUBBLE_SEASON)
            for code in ("UTA", "DEN"):
                team = core.get_or_create_team(
                    basketball_reference_team_id=code, current_abbreviation=code
                )
                core.get_or_create_team_season(team=team, season=season, team_abbreviation=code)
            assert _load_bubble(session).status == "loaded"
            session.commit()
        # What the pre-F8-024 loaders stored: SQL, so `updated_at` is left as it was.
        windows = "C:\\Users\\someone\\repo\\data\\raw\\html\\" + BUBBLE_KEY.replace("/", "\\")
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE stats.team_game_totals SET cache_path = :p"), {"p": windows}
            )
            connection.execute(
                text("UPDATE stats.player_game_totals SET cache_path = :p"),
                {"p": "data/raw/html/" + BUBBLE_KEY},
            )
    finally:
        engine.dispose()
    legacy = _game_rows(scratch_url)
    assert {row[1] for row in legacy["player_game_totals"]} == {"data/raw/html/" + BUBBLE_KEY}

    _run_ok(scratch_url, "upgrade", TARGET)

    upgraded = _game_rows(scratch_url)
    expected = {
        table: [(row_id, BUBBLE_KEY, stamp) for row_id, _, stamp in rows]
        for table, rows in legacy.items()
    }
    assert upgraded == expected

    engine = create_engine(scratch_url)
    try:
        with Session(engine) as session:
            result = _load_bubble(session)
            assert result.status == "unchanged"
            assert result.players_created == ()
            assert not session.dirty and not session.new and not session.deleted
            session.commit()
    finally:
        engine.dispose()
    assert _game_rows(scratch_url) == upgraded
