"""Apply the latest schedule snapshots and cached box scores to `core.games` (F8-014).

One run has three steps, and only the snapshots and the archive cache are read:

1. **Check.** Every linked month must have a usable snapshot, and every schedule
   row must agree with what is stored. A difference on a `final` row, or on a
   field of any row that may not change, is a conflict: the run fails and writes
   nothing.
2. **Schedule.** New games, status transitions, and the mutable fields are
   applied in one transaction. A stored `scheduled` game the latest snapshots no
   longer list is `postponed`, never deleted.
3. **Results.** Each scored game not yet `final` whose box score is cached goes
   through F8-005's `load_game`, in its own transaction. A quarantined or
   missing box score leaves the game `scheduled`.

`neutral_site` stays NULL for the whole season in progress. F8-005's inference
takes a team's home city from its season's venues, which a partial season cannot
establish, and a later pass would have to change `final` rows.

`--as-of` is the owner's run date; no clock is read. It bounds the season and
names the games that should already have a score.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nba_data.db.models import Game, TeamGameTotals
from nba_data.db.repositories.games import GameRepository, TeamSeasonKey
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.current_season_planning import (
    require_as_of_in_season,
    require_latest_month_pages,
)
from nba_data.scraping.game_pilot_manifest import box_score_url
from nba_data.scraping.loaders.current_season_identity import (
    CurrentSeasonLoadError,
    require_current_season,
)
from nba_data.scraping.loaders.games import GameLineage, load_game, parse_start_time
from nba_data.scraping.parsers.box_score import parse_box_score_page
from nba_data.scraping.parsers.league_schedule import ScheduleGame
from nba_data.scraping.snapshot_cache import SnapshotCache
from nba_data.validation.parser_contracts import current_parser_version

STATUS_SCHEDULED = "scheduled"
STATUS_FINAL = "final"
STATUS_POSTPONED = "postponed"
FIELDS_UPDATED = "scheduled_fields_updated"

_POSTPONED_NOTE = "postponed"

DEFAULT_PARSER_VERSION = current_parser_version("box_score")


@dataclass
class CurrentSeasonGamesReport:
    season_end_year: int
    as_of: date
    parser_version: str
    schedule_rows: int = 0
    transitions: Counter[str] = field(default_factory=Counter)
    statuses: dict[str, int] = field(default_factory=dict)
    conflicts: dict[str, list[str]] = field(default_factory=dict)
    missing_box_score: list[str] = field(default_factory=list)
    scored_without_link: list[str] = field(default_factory=list)
    unscored_before_as_of: list[str] = field(default_factory=list)
    quarantined: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    warnings: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    players_created: list[str] = field(default_factory=list)

    @property
    def run_failed(self) -> bool:
        """A game still waiting for its box score is coverage, not a failure."""

        return bool(self.conflicts or self.quarantined or self.failed)

    def to_dict(self) -> dict[str, object]:
        return {
            "season_end_year": self.season_end_year,
            "as_of": self.as_of.isoformat(),
            "parser_version": self.parser_version,
            "schedule_rows": self.schedule_rows,
            "transitions": dict(sorted(self.transitions.items())),
            "statuses": dict(sorted(self.statuses.items())),
            "conflicts": dict(sorted(self.conflicts.items())),
            "missing_box_score": sorted(self.missing_box_score),
            "scored_without_link": sorted(self.scored_without_link),
            "unscored_before_as_of": sorted(self.unscored_before_as_of),
            "quarantined": dict(sorted(self.quarantined.items())),
            "failed": dict(sorted(self.failed.items())),
            "warnings": dict(sorted(self.warnings.items())),
            "players_created": sorted(self.players_created),
            "run_failed": self.run_failed,
        }


@dataclass(frozen=True)
class _Row:
    game_id: str
    game: ScheduleGame
    home: TeamSeasonKey
    away: TeamSeasonKey
    start_time: time | None

    @property
    def marked_postponed(self) -> bool:
        return not self.game.played and _POSTPONED_NOTE in (self.game.notes or "").casefold()


def build_game_id(game_date: date, home_code: str) -> str:
    """Basketball Reference's id: `<yyyymmdd>0<home code>`, from the home team's link code."""

    return f"{game_date:%Y%m%d}0{home_code}"


def run_current_season_games(
    session: Session,
    *,
    snapshots: SnapshotCache,
    archive: HtmlCache,
    season_end_year: int,
    as_of: date,
    parser_version: str = DEFAULT_PARSER_VERSION,
) -> CurrentSeasonGamesReport:
    """Apply the latest snapshots. Raises, having written nothing, if they are unusable."""

    require_current_season(season_end_year)
    require_as_of_in_season(as_of, season_end_year)
    games = schedule_rows(snapshots, season_end_year)
    return apply_schedule(
        session,
        games,
        archive=archive,
        season_end_year=season_end_year,
        as_of=as_of,
        parser_version=parser_version,
    )


def schedule_rows(snapshots: SnapshotCache, season_end_year: int) -> tuple[ScheduleGame, ...]:
    """Every row of the latest month snapshots, which must all exist."""

    pages = require_latest_month_pages(snapshots, season_end_year)
    return tuple(game for page in pages.values() for game in page.games)


def apply_schedule(
    session: Session,
    games: tuple[ScheduleGame, ...],
    *,
    archive: HtmlCache,
    season_end_year: int,
    as_of: date,
    parser_version: str = DEFAULT_PARSER_VERSION,
) -> CurrentSeasonGamesReport:
    report = CurrentSeasonGamesReport(
        season_end_year=season_end_year,
        as_of=as_of,
        parser_version=parser_version,
        schedule_rows=len(games),
    )
    season_id, rows = _resolve_rows(session, games, season_end_year, report)
    stored = {
        game.basketball_reference_game_id: game
        for game in session.scalars(select(Game).where(Game.season_id == season_id))
    }
    _require_months_observed(rows, stored)
    _find_conflicts(session, rows, stored, report)
    if report.conflicts:
        _record_statuses(session, season_id, report)
        session.rollback()
        return report

    final_before = {game_id for game_id, game in stored.items() if game.status == STATUS_FINAL}
    try:
        _apply_schedule_rows(session, rows, stored, season_id, report)
        session.commit()
    except Exception:
        session.rollback()
        raise

    for row in rows:
        if row.game_id not in final_before:
            _load_result(session, row, archive, season_end_year, parser_version, report)

    _record_statuses(session, season_id, report)
    session.rollback()
    return report


def _resolve_rows(
    session: Session,
    games: tuple[ScheduleGame, ...],
    season_end_year: int,
    report: CurrentSeasonGamesReport,
) -> tuple[int, list[_Row]]:
    repository = GameRepository(session)
    season_id = repository.season_id(season_end_year)
    if season_id is None:
        msg = f"Season {season_end_year} is not loaded; run backfill current-season-identity first"
        raise CurrentSeasonLoadError(msg)
    codes = {code for game in games for code in (game.visitor_code, game.home_code)}
    team_seasons = repository.team_seasons(season_end_year, codes)
    missing = sorted(codes - set(team_seasons))
    if missing:
        msg = f"No {season_end_year} team-season for: {', '.join(missing)}"
        raise CurrentSeasonLoadError(msg)

    rows: list[_Row] = []
    seen: set[str] = set()
    for game in games:
        game_id = build_game_id(game.game_date, game.home_code)
        if game.game_id is not None and game.game_id != game_id:
            msg = f"Schedule link {game.game_id} differs from the built game id {game_id}"
            raise CurrentSeasonLoadError(msg)
        if game_id in seen:
            msg = f"Game {game_id} is listed twice in the latest snapshots"
            raise CurrentSeasonLoadError(msg)
        seen.add(game_id)
        try:
            start_time = parse_start_time(game.start_time)
        except ValueError as exc:
            msg = f"Game {game_id}: {exc}"
            raise CurrentSeasonLoadError(msg) from exc
        rows.append(
            _Row(
                game_id=game_id,
                game=game,
                home=team_seasons[game.home_code],
                away=team_seasons[game.visitor_code],
                start_time=start_time,
            )
        )
        if game.game_date < report.as_of and not game.played:
            report.unscored_before_as_of.append(game_id)
        if game.game_id is None and game.visitor_points is not None:
            report.scored_without_link.append(game_id)
    return season_id, rows


def _require_months_observed(rows: list[_Row], stored: dict[str, Game]) -> None:
    """Raise if a stored game's month is absent: a dropped month must not read as postponed."""

    observed = {f"{row.game.game_date:%Y-%m}" for row in rows}
    listed = {row.game_id for row in rows}
    absent = sorted(
        {
            f"{game.game_date:%Y-%m}"
            for game_id, game in stored.items()
            if game.status == STATUS_SCHEDULED
            and game_id not in listed
            and f"{game.game_date:%Y-%m}" not in observed
        }
    )
    if absent:
        msg = f"The latest snapshots list no game for stored months: {', '.join(absent)}"
        raise CurrentSeasonLoadError(msg)


def _find_conflicts(
    session: Session,
    rows: list[_Row],
    stored: dict[str, Game],
    report: CurrentSeasonGamesReport,
) -> None:
    points = _final_points(session, stored)
    listed = {row.game_id for row in rows}
    report.conflicts.update(
        {
            game_id: ["a final game is no longer listed"]
            for game_id, game in stored.items()
            if game.status == STATUS_FINAL and game_id not in listed
        }
    )
    for row in rows:
        stored_game = stored.get(row.game_id)
        if stored_game is None:
            continue
        differences = _identity_differences(stored_game, row)
        if stored_game.status == STATUS_FINAL:
            differences.extend(
                _final_differences(stored_game, row, points.get(stored_game.id, {}))
            )
        if differences:
            report.conflicts[row.game_id] = differences


def _identity_differences(game: Game, row: _Row) -> list[str]:
    differences: list[str] = []
    if game.game_date != row.game.game_date:
        differences.append(f"game_date {game.game_date} -> {row.game.game_date}")
    if game.home_team_season_id != row.home.team_season_id:
        differences.append("home team differs")
    if game.away_team_season_id != row.away.team_season_id:
        differences.append("away team differs")
    return differences


def _final_differences(game: Game, row: _Row, points: dict[int, int | None]) -> list[str]:
    schedule = row.game
    differences: list[str] = []
    if not schedule.played:
        differences.append("a final game has no score on the latest snapshot")
    else:
        stored_score = (points.get(row.away.team_season_id), points.get(row.home.team_season_id))
        published = (schedule.visitor_points, schedule.home_points)
        if stored_score != published:
            differences.append(f"score {stored_score} -> {published}")
    if game.start_time_et != row.start_time:
        differences.append(f"start_time_et {game.start_time_et} -> {row.start_time}")
    if not _same_venue(game.venue, schedule.arena):
        differences.append(f"venue {game.venue} -> {schedule.arena}")
    return differences


def _same_venue(stored: str | None, arena: str | None) -> bool:
    """A final game holds the box score's 'Arena, City, State'; the schedule names the arena."""

    if stored is None or arena is None:
        return stored == arena
    return stored == arena or stored.startswith(f"{arena},")


def _final_points(session: Session, stored: dict[str, Game]) -> dict[int, dict[int, int | None]]:
    final_ids = [game.id for game in stored.values() if game.status == STATUS_FINAL]
    points: dict[int, dict[int, int | None]] = {}
    if not final_ids:
        return points
    statement = select(
        TeamGameTotals.game_id, TeamGameTotals.team_season_id, TeamGameTotals.pts
    ).where(TeamGameTotals.game_id.in_(final_ids))
    for game_id, team_season_id, pts in session.execute(statement):
        points.setdefault(game_id, {})[team_season_id] = pts
    return points


def _apply_schedule_rows(
    session: Session,
    rows: list[_Row],
    stored: dict[str, Game],
    season_id: int,
    report: CurrentSeasonGamesReport,
) -> None:
    listed = {row.game_id for row in rows}
    for row in rows:
        desired = STATUS_POSTPONED if row.marked_postponed else STATUS_SCHEDULED
        game = stored.get(row.game_id)
        if game is None:
            session.add(
                Game(
                    basketball_reference_game_id=row.game_id,
                    season_id=season_id,
                    home_team_season_id=row.home.team_season_id,
                    away_team_season_id=row.away.team_season_id,
                    game_date=row.game.game_date,
                    start_time_et=row.start_time,
                    status=desired,
                    venue=row.game.arena,
                )
            )
            report.transitions[f"new->{desired}"] += 1
            continue
        if game.status == STATUS_FINAL:
            continue
        if game.status != desired:
            report.transitions[f"{game.status}->{desired}"] += 1
            game.status = desired
        if game.start_time_et != row.start_time or game.venue != row.game.arena:
            game.start_time_et = row.start_time
            game.venue = row.game.arena
            report.transitions[FIELDS_UPDATED] += 1

    for game_id, game in stored.items():
        if game.status == STATUS_SCHEDULED and game_id not in listed:
            game.status = STATUS_POSTPONED
            report.transitions[f"{STATUS_SCHEDULED}->{STATUS_POSTPONED}"] += 1
    session.flush()


def _load_result(
    session: Session,
    row: _Row,
    archive: HtmlCache,
    season_end_year: int,
    parser_version: str,
    report: CurrentSeasonGamesReport,
) -> None:
    if not row.game.played:
        return
    url = box_score_url(row.game_id)
    lineage = GameLineage(
        source_url=url,
        cache_path=str(archive.path_for_url(url)),
        parser_version=parser_version,
    )
    try:
        html = archive.get(url)
        if html is None:
            report.missing_box_score.append(row.game_id)
            return
        result = load_game(
            session,
            row.game,
            parse_box_score_page(html),
            lineage,
            season_end_year=season_end_year,
        )
        if result.status == "quarantined":
            session.rollback()
        else:
            session.commit()
    except Exception as exc:  # one game's failure must not take the others with it
        session.rollback()
        report.failed[row.game_id] = f"{type(exc).__name__}: {exc}"
        return

    if result.warnings:
        report.warnings[row.game_id] = [issue.to_dict() for issue in result.warnings]
    if result.status == "quarantined":
        report.quarantined[row.game_id] = [issue.to_dict() for issue in result.quarantine]
        return
    report.transitions[f"{STATUS_SCHEDULED}->{STATUS_FINAL}"] += 1
    report.players_created.extend(result.players_created)


def _record_statuses(
    session: Session,
    season_id: int,
    report: CurrentSeasonGamesReport,
) -> None:
    statement = (
        select(Game.status, func.count()).where(Game.season_id == season_id).group_by(Game.status)
    )
    report.statuses = {status: count for status, count in session.execute(statement)}


__all__ = [
    "DEFAULT_PARSER_VERSION",
    "FIELDS_UPDATED",
    "CurrentSeasonGamesReport",
    "apply_schedule",
    "build_game_id",
    "run_current_season_games",
    "schedule_rows",
]
