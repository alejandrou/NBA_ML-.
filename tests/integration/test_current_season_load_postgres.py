"""The current-season loaders against PostgreSQL, with every constraint in force.

A scheduled row has no game type, and only PostgreSQL runs the game id format
check. The rebuild fixture holds one finished season and the 2027 identity, to
prove the archive validators keep ignoring the season in progress.

Authorization, revision checking, and rollback belong to `conftest.py`.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import nba_data.scraping.loaders.current_season_games as games_module
from nba_data.db.models import Game, PlayerSeason, Season, TeamGameTotals, TeamSeason
from nba_data.db.repositories import CoreRepository
from nba_data.scraping.cache import CacheFetchMetadata, HtmlCache
from nba_data.scraping.current_season_planning import team_page_url
from nba_data.scraping.game_pilot_manifest import box_score_url, league_schedule_url
from nba_data.scraping.loaders.current_season_games import apply_schedule
from nba_data.scraping.loaders.current_season_identity import run_current_season_identity
from nba_data.scraping.parsers.box_score import (
    COUNTING_STATS,
    GAME_TYPE_REGULAR_SEASON,
    PARTICIPATION_PLAYED,
    BoxScorePlayerLine,
    BoxScoreTeam,
    ParsedBoxScore,
)
from nba_data.scraping.parsers.league_schedule import ScheduleGame
from nba_data.scraping.snapshot_cache import SnapshotCache
from nba_data.validation.official_stats import validate_official_stats
from nba_data.validation.offline_database import (
    OfflineDatabaseValidationExpectations,
    validate_offline_database,
)

pytestmark = pytest.mark.integration

TEAMS = tuple(f"T{chr(65 + index // 26)}{chr(65 + index % 26)}" for index in range(30))
AS_OF = date(2026, 11, 1)
FINISHED = ScheduleGame(
    game_date=date(2026, 10, 24),
    visitor_code=TEAMS[0],
    visitor_name="V",
    home_code=TEAMS[1],
    home_name="H",
    game_id=f"202610240{TEAMS[1]}",
    visitor_points=101,
    home_points=99,
    start_time="7:30p",
    arena="Arena",
)
UPCOMING = ScheduleGame(
    game_date=date(2026, 10, 30),
    visitor_code=TEAMS[2],
    visitor_name="V",
    home_code=TEAMS[3],
    home_name="H",
    start_time="8:00p",
    arena="Arena",
)


def _team(code: str, points: int) -> BoxScoreTeam:
    shares = [points // 5] * 5
    shares[0] += points - sum(shares)
    lines = tuple(
        BoxScorePlayerLine(
            player_id=f"{code.lower()}pl{index}",
            name=f"{code} Player {index}",
            starter=True,
            participation=PARTICIPATION_PLAYED,
            seconds_played=2880,
            stats={**dict.fromkeys(COUNTING_STATS, 1), "pts": share},
            plus_minus=0,
        )
        for index, share in enumerate(shares)
    )
    totals: dict[str, int | None] = {**dict.fromkeys(COUNTING_STATS, 5), "pts": points}
    return BoxScoreTeam(
        code=code,
        name=code,
        scorebox_points=points,
        line_score=(points - 75, 25, 25, 25),
        line_score_total=points,
        totals_seconds=14400,
        totals=totals,
        players=lines,
        inactive_players=(),
    )


def _fake_parse(_html: str) -> ParsedBoxScore:
    return ParsedBoxScore(
        visitor=_team(FINISHED.visitor_code, 101),
        home=_team(FINISHED.home_code, 99),
        period_labels=("1", "2", "3", "4"),
        scorebox_meta=(),
        attendance=18000,
        play_by_play_linked=True,
        issues=(),
        heading="Box Score",
        game_type=GAME_TYPE_REGULAR_SEASON,
        venue="Arena, City, State",
    )


def _schedule_html() -> str:
    rows = "".join(
        '<tr><th data-stat="date_game">Sat, Oct 24, 2026</th>'
        f'<td data-stat="visitor_team_name"><a href="/teams/{TEAMS[i]}/2027.html">V</a></td>'
        f'<td data-stat="home_team_name"><a href="/teams/{TEAMS[i + 1]}/2027.html">H</a></td></tr>'
        for i in range(0, 30, 2)
    )
    return (
        '<html><body><a href="/leagues/NBA_2027_games-october.html">October</a>'
        f'<table id="schedule"><tbody>{rows}</tbody></table></body></html>'
    )


def _snapshots(root: Path) -> SnapshotCache:
    cache = SnapshotCache(root)
    moment = datetime(2026, 10, 25, tzinfo=UTC)
    pages = {
        league_schedule_url(2027): _schedule_html(),
        league_schedule_url(2027, "october"): _schedule_html(),
        **{
            team_page_url(code, 2027): (
                f"<html><body><h1><span>2026-27</span><span>{code} Name</span>"
                "<span>Roster</span></h1></body></html>"
            )
            for code in TEAMS
        },
    }
    for url, html in pages.items():
        moment += timedelta(seconds=7)
        cache.write(url, html, CacheFetchMetadata(fetched_at=moment, http_status=200, final_url=url))
    return cache


def _seed_finished_season(session: Session) -> None:
    core = CoreRepository(session)
    season = core.get_or_create_season(league="NBA", season_year=2026)
    player = core.get_or_create_player(
        basketball_reference_player_id="archive01", full_name="Archive Player"
    )
    player_season = core.get_or_create_player_season(player=player, season=season)
    for code in TEAMS:
        team = core.get_or_create_team(
            basketball_reference_team_id=code, current_abbreviation=code, current_name=f"{code} Name"
        )
        core.get_or_create_team_alias(team=team, abbreviation=code, name=code, season_year=2026)
        team_season = core.get_or_create_team_season(
            team=team, season=season, team_abbreviation=code
        )
        core.get_or_create_player_team_season(player_season=player_season, team_season=team_season)
    session.commit()


def _archive(root: Path) -> HtmlCache:
    archive = HtmlCache(root)
    assert FINISHED.game_id is not None
    archive.set(box_score_url(FINISHED.game_id), "box score")
    return archive


def _status(session: Session, game_id: str) -> str | None:
    session.expire_all()
    return session.scalar(select(Game.status).where(Game.basketball_reference_game_id == game_id))


def test_identity_then_games_load_and_refresh(
    postgres_session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(games_module, "parse_box_score_page", _fake_parse)
    _seed_finished_season(postgres_session)
    run_current_season_identity(
        postgres_session, snapshots=_snapshots(tmp_path / "snapshots"), season_end_year=2027
    )
    archive = _archive(tmp_path / "cache")
    upcoming_id = f"202610300{TEAMS[3]}"

    first = apply_schedule(
        postgres_session, (FINISHED, UPCOMING), archive=archive, season_end_year=2027, as_of=AS_OF
    )

    assert not first.run_failed, first.to_dict()
    assert first.transitions == {"new->scheduled": 2, "scheduled->final": 1}
    assert FINISHED.game_id is not None
    assert _status(postgres_session, FINISHED.game_id) == "final"
    assert _status(postgres_session, upcoming_id) == "scheduled"
    assert postgres_session.scalar(select(func.count()).select_from(TeamGameTotals)) == 2

    unchanged = apply_schedule(
        postgres_session, (FINISHED, UPCOMING), archive=archive, season_end_year=2027, as_of=AS_OF
    )
    assert not unchanged.transitions

    postponed = apply_schedule(
        postgres_session, (FINISHED,), archive=archive, season_end_year=2027, as_of=AS_OF
    )
    assert postponed.transitions == {"scheduled->postponed": 1}
    assert _status(postgres_session, upcoming_id) == "postponed"

    conflict = apply_schedule(
        postgres_session,
        (replace(FINISHED, visitor_points=120),),
        archive=archive,
        season_end_year=2027,
        as_of=AS_OF,
    )
    assert conflict.run_failed
    assert list(conflict.conflicts) == [FINISHED.game_id]


def test_the_archive_validators_ignore_a_loaded_current_season(
    postgres_session: Session, tmp_path: Path
) -> None:
    _seed_finished_season(postgres_session)
    run_current_season_identity(
        postgres_session, snapshots=_snapshots(tmp_path), season_end_year=2027
    )
    season_2027 = postgres_session.scalar(select(Season).where(Season.season_year == 2027))
    assert season_2027 is not None
    assert (
        postgres_session.scalar(
            select(func.count())
            .select_from(TeamSeason)
            .where(TeamSeason.season_id == season_2027.id)
        )
        == 30
    )
    assert (
        postgres_session.scalar(
            select(func.count())
            .select_from(PlayerSeason)
            .where(PlayerSeason.season_id == season_2027.id)
        )
        == 0
    )

    offline = validate_offline_database(
        postgres_session,
        {
            "selected_inventory_entries": 30,
            "processing_report": {"validated_entries": 30, "failed_entries": 0},
            "load_report": {"loaded_entries": 30, "loaded_rows": 30, "failed_entries": 0},
            "audit_report": {"quarantined_entries": 0, "quarantined_rows": 0},
        },
        OfflineDatabaseValidationExpectations(
            table_counts={
                "core.seasons": 1,
                "core.teams": 30,
                "core.team_aliases": 30,
                "core.team_seasons": 30,
                "core.players": 1,
                "core.player_seasons": 1,
                "core.player_team_seasons": 30,
            },
            expected_start_year=2026,
            expected_end_year=2026,
            min_team_seasons_per_season=30,
            min_player_seasons_per_season=1,
            min_player_team_seasons_per_season=30,
            expected_backfill_selected_inventory_entries=30,
            expected_backfill_loaded_entries=30,
            expected_backfill_loaded_rows=30,
        ),
    )
    assert offline.passed, offline.to_dict()

    official = validate_official_stats(
        postgres_session,
        coverage_artifact={
            "schema_version": 1,
            "cache_root": "/fake/cache",
            "parser_contracts": {},
            "cache_fingerprint": {"digest": "0" * 64, "player_page_count": 0, "team_page_count": 0},
            "counts": {},
            "entries": [
                {
                    "basketball_reference_player_id": "newplayer01",
                    "season_year": 2027,
                    "regular_aggregate_tables": ["stats.player_season_totals"],
                    "postseason_aggregate_tables": [],
                    "regular_team_stints": [],
                    "postseason_team_stints": [],
                    "did_not_play": {"regular": False, "postseason": False},
                }
            ],
            "unexplained": [],
            "disagreements": [],
            "source_issues": [],
        },
    )
    assert not [issue for issue in official.issues if issue.code.startswith("coverage_")]
    scope = official.coverage_summary["dimensions"]["regular_aggregate"]["scope"]
    assert scope["season_years"] == [2026]
    assert scope["excluded_seasons"] == [2027]
