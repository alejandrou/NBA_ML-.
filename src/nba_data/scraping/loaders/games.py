"""Load one finished game from its schedule row and box score (F8-005).

`load_game` writes one `core.games` row, the two `stats.team_game_totals` rows,
and one `stats.player_game_totals` row per player line and inactive entry,
matching each on its natural key. Before any write it enforces the cross-table
rules the schema cannot (`docs/domain/BUSINESS_RULES.md`, "Games and Box
Scores"). A game that fails a gate is quarantined: it writes nothing and its
result names every reason. Disagreements in data that is not stored — the line
score — are warnings, never quarantines.

The gates reuse the pilot's reconciliation (`validation/game_pilot.py`), so
the loader accepts exactly what the pilot accepted: team turnovers that no
player line carries, and nothing read from a blank cell.

`derive_neutral_sites` is the second pass: once a season is loaded, a game is
neutral when its venue city differs from the city of most of its home team's
home games that season.

The caller owns the transaction; nothing here commits.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import time
from typing import Any, Literal

from sqlalchemy.orm import Session

from nba_data.db.repositories.games import FinalGameVenue, GameRepository, TeamSeasonKey
from nba_data.scraping.parsers.box_score import (
    COUNTING_STATS,
    GAME_TYPE_CUP_FINAL,
    GAME_TYPE_PLAY_IN,
    GAME_TYPE_PLAYOFFS,
    GAME_TYPE_REGULAR_SEASON,
    PARTICIPATION_DID_NOT_DRESS,
    PARTICIPATION_DID_NOT_PLAY,
    PARTICIPATION_INACTIVE,
    PARTICIPATION_NOT_WITH_TEAM,
    PARTICIPATION_OTHER_ABSENCE,
    PARTICIPATION_PLAYED,
    PARTICIPATION_SUSPENDED,
    BoxScorePlayerLine,
    BoxScoreTeam,
    ParsedBoxScore,
)
from nba_data.scraping.parsers.league_schedule import ScheduleGame
from nba_data.scraping.parsers.play_by_play import REGULATION_PERIODS
from nba_data.validation.game_pilot import minutes_problem, player_totals_problem

STATUS_FINAL = "final"
INACTIVE_REASON = "Inactive"

QUARANTINE_UNKNOWN_GAME_TYPE = "unknown_game_type"
QUARANTINE_MISSING_TEAM_SEASON = "missing_team_season"
QUARANTINE_TEAM_MISMATCH = "team_mismatch"
QUARANTINE_SCORE_MISMATCH = "score_mismatch"
QUARANTINE_TIED_SCORE = "tied_score"
QUARANTINE_MISSING_TEAM_TOTALS = "missing_team_totals"
QUARANTINE_PLAYER_SUM_MISMATCH = "player_sum_mismatch"
QUARANTINE_UNKNOWN_PARTICIPATION = "unknown_participation"
QUARANTINE_PLAYED_WITHOUT_SECONDS = "played_without_seconds"
# Fail-closed reasons beyond the card's list: malformed input is a failed gate,
# never an exception or a silently dropped value.
QUARANTINE_DUPLICATE_PLAYER = "duplicate_player"
QUARANTINE_UNNAMED_PLAYER = "unnamed_player"
QUARANTINE_UNREADABLE_START_TIME = "unreadable_start_time"
QUARANTINE_BOX_SCORE_UNREADABLE = "box_score_unreadable"
QUARANTINE_MINUTES_MISMATCH = "minutes_mismatch"
QUARANTINE_GAME_ID_MISMATCH = "game_id_mismatch"
QUARANTINE_INVALID_VALUES = "invalid_box_score_values"

WARNING_LINE_SCORE_UNREADABLE = "line_score_unreadable"
WARNING_LINE_SCORE_DISAGREES = "line_score_disagrees"
WARNING_CUP_FINAL_PLUS_MINUS_ZEROS = "cup_final_plus_minus_zeros"
WARNING_HOME_CITY_TIED = "home_city_tied"
WARNING_NEUTRAL_SITE_DEFERRED = "neutral_site_deferred"

STORED_GAME_TYPES = frozenset(
    {GAME_TYPE_REGULAR_SEASON, GAME_TYPE_PLAY_IN, GAME_TYPE_PLAYOFFS, GAME_TYPE_CUP_FINAL}
)
PARTICIPATIONS = frozenset(
    {
        PARTICIPATION_PLAYED,
        PARTICIPATION_DID_NOT_PLAY,
        PARTICIPATION_DID_NOT_DRESS,
        PARTICIPATION_NOT_WITH_TEAM,
        PARTICIPATION_SUSPENDED,
        PARTICIPATION_OTHER_ABSENCE,
        PARTICIPATION_INACTIVE,
    }
)

# Parser issues a gate already judges: the game type, the scorebox teams, and
# the team boxes. The line score is not stored, so its issues are warnings.
_GATED_PARSE_ISSUES = frozenset(
    {
        "heading_missing",
        "game_type_unrecognized",
        "scorebox_teams_unreadable",
        "basic_box_missing",
        "team_totals_missing",
    }
)
_LINE_SCORE_PARSE_ISSUES = frozenset(
    {"line_score_missing", "line_score_row_unreadable", "line_score_shape"}
)
_START_TIME_RE = re.compile(r"^(?P<hour>[0-9]{1,2}):(?P<minute>[0-5][0-9])\s*(?P<half>[ap])m?$")

LoadStatus = Literal["loaded", "unchanged", "quarantined"]


@dataclass(frozen=True)
class GameLineage:
    """Where a game's box score rows came from: stamped on both stats tables."""

    source_url: str
    cache_path: str
    parser_version: str


@dataclass(frozen=True)
class GameIssue:
    code: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class GameLoadResult:
    game_id: str
    status: LoadStatus
    game_type: str | None
    quarantine: tuple[GameIssue, ...] = ()
    warnings: tuple[GameIssue, ...] = ()
    players_created: tuple[str, ...] = ()


@dataclass(frozen=True)
class NeutralSiteResult:
    neutral_games: tuple[tuple[str, str], ...]
    updated: int
    warnings: tuple[GameIssue, ...]


def load_game(
    session: Session,
    parsed_schedule_row: ScheduleGame,
    parsed_box_score: ParsedBoxScore,
    lineage: GameLineage,
    *,
    season_end_year: int,
) -> GameLoadResult:
    """Gate, then upsert one finished game. Writes nothing when any gate fails."""

    schedule = parsed_schedule_row
    box = parsed_box_score
    game_id = schedule.game_id
    if game_id is None:
        msg = "Only a played schedule row, which carries a box score id, can be loaded"
        raise ValueError(msg)
    _require_lineage(lineage)

    quarantine, warnings = check_game(schedule, box)
    start_time, start_time_issue = _start_time(schedule.start_time)
    if start_time_issue is not None:
        quarantine.append(start_time_issue)

    repository = GameRepository(session)
    team_seasons: dict[str, TeamSeasonKey] = {}
    if box.visitor is not None and box.home is not None:
        codes = (box.visitor.code, box.home.code)
        team_seasons = repository.team_seasons(season_end_year, codes)
        missing = [code for code in codes if code not in team_seasons]
        if missing:
            quarantine.append(
                GameIssue(
                    QUARANTINE_MISSING_TEAM_SEASON,
                    f"{', '.join(missing)} {season_end_year} not in core.team_seasons",
                )
            )

    names = _player_names(box)
    known = repository.player_ids(names)
    unnamed = sorted(player for player, name in names.items() if player not in known and not name)
    if unnamed:
        quarantine.append(
            GameIssue(QUARANTINE_UNNAMED_PLAYER, f"no link text to create {', '.join(unnamed)}")
        )

    if quarantine:
        return GameLoadResult(
            game_id=game_id,
            status="quarantined",
            game_type=box.game_type,
            quarantine=tuple(quarantine),
            warnings=tuple(warnings),
        )

    assert box.visitor is not None and box.home is not None  # the team gate guarantees both
    created: list[str] = []
    player_ids = dict(known)
    for player in sorted(set(names) - set(known)):
        player_ids[player] = repository.create_player(
            basketball_reference_player_id=player, full_name=names[player]
        )
        created.append(player)

    visitor_key = team_seasons[box.visitor.code]
    home_key = team_seasons[box.home.code]
    stored_game_id, game_changed = repository.upsert_game(
        basketball_reference_game_id=game_id,
        values={
            "season_id": home_key.season_id,
            "home_team_season_id": home_key.team_season_id,
            "away_team_season_id": visitor_key.team_season_id,
            "game_date": schedule.game_date,
            "start_time_et": start_time,
            "game_type": box.game_type,
            "status": STATUS_FINAL,
            "venue": box.venue,
            "attendance": box.attendance,
        },
    )

    lineage_values = {
        "source_url": lineage.source_url,
        "cache_path": lineage.cache_path,
        "parser_version": lineage.parser_version,
    }
    changed = game_changed or bool(created)
    changed |= repository.remove_other_team_totals(
        game_id=stored_game_id,
        team_season_ids=(visitor_key.team_season_id, home_key.team_season_id),
    )
    null_plus_minus = _cup_final_plus_minus_is_noise(box)
    if null_plus_minus:
        warnings.append(
            GameIssue(
                WARNING_CUP_FINAL_PLUS_MINUS_ZEROS,
                "every played line has plus-minus 0; stored as NULL",
            )
        )

    lines: dict[int, dict[str, Any]] = {}
    for team, key, is_home in ((box.visitor, visitor_key, False), (box.home, home_key, True)):
        changed |= repository.upsert_team_game_totals(
            game_id=stored_game_id,
            team_season_id=key.team_season_id,
            values={**_team_values(team, is_home=is_home), **lineage_values},
        )
        for line in team.players:
            lines[player_ids[line.player_id]] = {
                **_line_values(line, null_plus_minus=null_plus_minus),
                "team_season_id": key.team_season_id,
                **lineage_values,
            }
        for inactive in team.inactive_players:
            lines[player_ids[inactive.player_id]] = {
                **_inactive_values(),
                "team_season_id": key.team_season_id,
                **lineage_values,
            }
    changed |= repository.replace_player_game_totals(game_id=stored_game_id, rows=lines)

    return GameLoadResult(
        game_id=game_id,
        status="loaded" if changed else "unchanged",
        game_type=box.game_type,
        warnings=tuple(warnings),
        players_created=tuple(created),
    )


def check_game(
    schedule: ScheduleGame,
    box: ParsedBoxScore,
) -> tuple[list[GameIssue], list[GameIssue]]:
    """The gates that need no database: (quarantine reasons, warnings)."""

    quarantine: list[GameIssue] = []
    warnings: list[GameIssue] = []

    if box.game_type not in STORED_GAME_TYPES:
        quarantine.append(
            GameIssue(QUARANTINE_UNKNOWN_GAME_TYPE, f"heading {box.heading!r} names no known type")
        )

    unreadable = sorted(
        {issue.code for issue in box.issues} - _GATED_PARSE_ISSUES - _LINE_SCORE_PARSE_ISSUES
    )
    if unreadable:
        quarantine.append(GameIssue(QUARANTINE_BOX_SCORE_UNREADABLE, ", ".join(unreadable)))

    visitor, home = box.visitor, box.home
    if visitor is None or home is None:
        quarantine.append(GameIssue(QUARANTINE_TEAM_MISMATCH, "the box score names no two teams"))
        return quarantine, warnings

    schedule_teams = (schedule.visitor_code, schedule.home_code)
    box_teams = (visitor.code, home.code)
    id_home = (schedule.game_id or "")[-3:]
    if box_teams != schedule_teams or home.code != id_home or visitor.code == home.code:
        quarantine.append(
            GameIssue(
                QUARANTINE_TEAM_MISMATCH,
                f"schedule {schedule_teams}, box score {box_teams}, game id home {id_home}",
            )
        )

    if (schedule.game_id or "")[:8] != schedule.game_date.strftime("%Y%m%d"):
        quarantine.append(
            GameIssue(QUARANTINE_GAME_ID_MISMATCH, "game id date differs from schedule date")
        )

    totals_missing = [
        team.code
        for team in (visitor, home)
        if team.totals.get("pts") is None or team.totals_seconds is None
    ]
    if totals_missing:
        quarantine.append(
            GameIssue(
                QUARANTINE_MISSING_TEAM_TOTALS,
                f"no points or minutes total for {', '.join(totals_missing)}",
            )
        )

    scores = {
        "schedule": (schedule.visitor_points, schedule.home_points),
        "scorebox": (visitor.scorebox_points, home.scorebox_points),
    }
    if not totals_missing:
        scores["team_totals"] = (visitor.totals.get("pts"), home.totals.get("pts"))
    if len(set(scores.values())) != 1 or None in scores["schedule"] + scores["scorebox"]:
        detail = "; ".join(f"{source} {pair}" for source, pair in scores.items())
        quarantine.append(GameIssue(QUARANTINE_SCORE_MISMATCH, detail))
    else:
        visitor_points, home_points = scores["scorebox"]
        if visitor_points == home_points:
            quarantine.append(GameIssue(QUARANTINE_TIED_SCORE, f"{visitor_points}-{home_points}"))

    sum_problems = [
        f"{team.code}: {problem}"
        for team in (visitor, home)
        if (problem := player_totals_problem(team)) is not None
    ]
    if sum_problems:
        quarantine.append(GameIssue(QUARANTINE_PLAYER_SUM_MISMATCH, "; ".join(sum_problems)))

    invalid_values = []
    for team in (visitor, home):
        values = [team.totals_seconds, *team.totals.values()]
        values.extend(
            value for line in team.played_lines
            for value in (line.seconds_played, *line.stats.values())
        )
        if any(value is not None and value < 0 for value in values):
            invalid_values.append(f"{team.code}: negative seconds or counter")
    if box.attendance is not None and box.attendance < 0:
        invalid_values.append("negative attendance")
    if invalid_values:
        quarantine.append(GameIssue(QUARANTINE_INVALID_VALUES, "; ".join(invalid_values)))

    unknown_participation = [
        f"{line.player_id} {line.participation!r} ({line.reason!r})"
        for team in (visitor, home)
        for line in team.players
        if line.participation not in PARTICIPATIONS
        or (line.participation != PARTICIPATION_PLAYED and not (line.reason or "").strip())
    ]
    if unknown_participation:
        quarantine.append(
            GameIssue(QUARANTINE_UNKNOWN_PARTICIPATION, ", ".join(unknown_participation))
        )

    without_seconds = [
        line.player_id
        for team in (visitor, home)
        for line in team.played_lines
        if line.seconds_played is None
    ]
    if without_seconds:
        quarantine.append(GameIssue(QUARANTINE_PLAYED_WITHOUT_SECONDS, ", ".join(without_seconds)))

    minute_problems = [
        f"{team.code}: {problem}"
        for team in (visitor, home)
        if team.totals_seconds is not None
        and all(line.seconds_played is not None for line in team.played_lines)
        and (problem := minutes_problem(team, schedule.overtime_periods)) is not None
    ]
    if minute_problems:
        quarantine.append(GameIssue(QUARANTINE_MINUTES_MISMATCH, "; ".join(minute_problems)))

    listed = [
        player
        for team in (visitor, home)
        for player in (
            *(line.player_id for line in team.players),
            *team.inactive_player_ids,
        )
    ]
    duplicates = sorted(player for player, count in Counter(listed).items() if count > 1)
    if duplicates:
        quarantine.append(GameIssue(QUARANTINE_DUPLICATE_PLAYER, ", ".join(duplicates)))

    warnings.extend(_line_score_warnings(schedule, box, visitor, home))
    return quarantine, warnings


def parse_start_time(text: str | None) -> time | None:
    """'7:30p' -> 19:30, blank -> None; anything else raises ValueError."""

    if text is None or not text.strip():
        return None
    match = _START_TIME_RE.fullmatch(text.strip().lower())
    if match is None:
        msg = f"unreadable start time {text!r}"
        raise ValueError(msg)
    hour = int(match.group("hour"))
    if not 1 <= hour <= 12:
        msg = f"unreadable start time {text!r}"
        raise ValueError(msg)
    hour = hour % 12 + (12 if match.group("half") == "p" else 0)
    return time(hour, int(match.group("minute")))


def venue_city(venue: str | None) -> str | None:
    """The text after the venue's first comma: 'Accor Arena, Paris, France' -> 'Paris, France'."""

    if venue is None or "," not in venue:
        return None
    city = venue.split(",", maxsplit=1)[1].strip()
    return city or None


def neutral_sites(
    games: Sequence[FinalGameVenue],
) -> tuple[dict[int, bool | None], list[GameIssue]]:
    """Decide each game's `neutral_site` from one season's loaded games.

    A game is neutral when its venue city differs from the city of most of its
    home team's home games that season; no venue, or no single most common
    home city, leaves it undetermined (None).
    """

    cities_by_team: dict[int, Counter[str]] = defaultdict(Counter)
    for game in games:
        city = venue_city(game.venue)
        if city is not None:
            cities_by_team[game.home_team_season_id][city.casefold()] += 1

    home_cities: dict[int, str | None] = {}
    warnings: list[GameIssue] = []
    for team_season_id, cities in cities_by_team.items():
        ranked = cities.most_common()
        if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
            home_cities[team_season_id] = None
            tied = ", ".join(city for city, count in ranked if count == ranked[0][1])
            warnings.append(
                GameIssue(
                    WARNING_HOME_CITY_TIED,
                    f"team-season {team_season_id}: home games split evenly over {tied}",
                )
            )
        else:
            home_cities[team_season_id] = ranked[0][0]

    decided: dict[int, bool | None] = {}
    for game in games:
        city = venue_city(game.venue)
        home_city = home_cities.get(game.home_team_season_id)
        decided[game.game_id] = (
            None if city is None or home_city is None else city.casefold() != home_city
        )
    return decided, warnings


def derive_neutral_sites(
    session: Session,
    season_end_year: int,
    *,
    expected_game_ids: frozenset[str] | None = None,
) -> NeutralSiteResult:
    """Second pass over a loaded season: update `neutral_site` only, where it changed."""

    repository = GameRepository(session)
    season_id = repository.season_id(season_end_year)
    if season_id is None:
        return NeutralSiteResult(neutral_games=(), updated=0, warnings=())
    games = repository.final_game_venues(season_id)
    if expected_game_ids is not None and not expected_game_ids.issubset(
        game.basketball_reference_game_id for game in games
    ):
        return NeutralSiteResult(
            neutral_games=(), updated=0,
            warnings=(GameIssue(
                WARNING_NEUTRAL_SITE_DEFERRED,
                "neutral-site inference needs every selected game loaded; no flags changed",
            ),),
        )
    decided, warnings = neutral_sites(games)
    updated = 0
    for game in games:
        value = decided[game.game_id]
        if game.neutral_site != value:
            repository.set_neutral_site(game.game_id, value)
            updated += 1
    neutral = tuple(
        (game.basketball_reference_game_id, game.venue or "")
        for game in games
        if decided[game.game_id]
    )
    return NeutralSiteResult(neutral_games=neutral, updated=updated, warnings=tuple(warnings))


def _start_time(text: str | None) -> tuple[time | None, GameIssue | None]:
    try:
        return parse_start_time(text), None
    except ValueError as exc:
        return None, GameIssue(QUARANTINE_UNREADABLE_START_TIME, str(exc))


def _line_score_warnings(
    schedule: ScheduleGame,
    box: ParsedBoxScore,
    visitor: BoxScoreTeam,
    home: BoxScoreTeam,
) -> list[GameIssue]:
    parse_issues = sorted({issue.code for issue in box.issues} & _LINE_SCORE_PARSE_ISSUES)
    if parse_issues:
        return [GameIssue(WARNING_LINE_SCORE_UNREADABLE, ", ".join(parse_issues))]

    problems: list[str] = []
    expected_periods = REGULATION_PERIODS + schedule.overtime_periods
    for team in (visitor, home):
        final = team.totals.get("pts")
        for period, points in sorted(team.period_points.items()):
            if points is None or period > len(team.line_score):
                problems.append(f"{team.code}: period {period} box or line score unreadable")
            elif points != team.line_score[period - 1]:
                problems.append(
                    f"{team.code}: period {period} box {points}, "
                    f"line score {team.line_score[period - 1]}"
                )
        if len(team.line_score) != expected_periods:
            problems.append(
                f"{team.code}: {len(team.line_score)} periods, schedule implies {expected_periods}"
            )
        if team.line_score_total != final:
            problems.append(f"{team.code}: line score total {team.line_score_total}, final {final}")
        elif sum(team.line_score) != team.line_score_total:
            problems.append(
                f"{team.code}: periods sum to {sum(team.line_score)}, total {team.line_score_total}"
            )
    if problems:
        return [GameIssue(WARNING_LINE_SCORE_DISAGREES, "; ".join(problems))]
    return []


def _player_names(box: ParsedBoxScore) -> dict[str, str]:
    names: dict[str, str] = {}
    for team in box.teams:
        for line in team.players:
            names.setdefault(line.player_id, line.name.strip())
        for inactive in team.inactive_players:
            names.setdefault(inactive.player_id, inactive.name.strip())
    return names


def _cup_final_plus_minus_is_noise(box: ParsedBoxScore) -> bool:
    if box.game_type != GAME_TYPE_CUP_FINAL:
        return False
    published = [
        line.plus_minus
        for team in box.teams
        for line in team.played_lines
        if line.plus_minus is not None
    ]
    return bool(published) and all(value == 0 for value in published)


def _team_values(team: BoxScoreTeam, *, is_home: bool) -> dict[str, Any]:
    return {
        "is_home": is_home,
        "seconds_played": team.totals_seconds,
        **{stat: team.totals.get(stat) for stat in COUNTING_STATS},
    }


def _line_values(line: BoxScorePlayerLine, *, null_plus_minus: bool) -> dict[str, Any]:
    if line.participation != PARTICIPATION_PLAYED:
        return {
            **_absent_values(),
            "participation": line.participation,
            "participation_reason": line.reason,
        }
    return {
        "starter": line.starter,
        "participation": PARTICIPATION_PLAYED,
        "participation_reason": None,
        "seconds_played": line.seconds_played,
        **{stat: line.stats.get(stat) for stat in COUNTING_STATS},
        "plus_minus": None if null_plus_minus else line.plus_minus,
    }


def _inactive_values() -> dict[str, Any]:
    return {
        **_absent_values(),
        "participation": PARTICIPATION_INACTIVE,
        "participation_reason": INACTIVE_REASON,
    }


def _absent_values() -> dict[str, Any]:
    """A line that is not `played` is never a starter and carries no stat at all."""

    return {
        "starter": False,
        "seconds_played": None,
        **dict.fromkeys(COUNTING_STATS),
        "plus_minus": None,
    }


def _require_lineage(lineage: GameLineage) -> None:
    for field_name in ("source_url", "cache_path", "parser_version"):
        if not getattr(lineage, field_name).strip():
            msg = f"{field_name} is required"
            raise ValueError(msg)


__all__ = [
    "PARTICIPATIONS",
    "QUARANTINE_BOX_SCORE_UNREADABLE",
    "QUARANTINE_DUPLICATE_PLAYER",
    "QUARANTINE_GAME_ID_MISMATCH",
    "QUARANTINE_INVALID_VALUES",
    "QUARANTINE_MINUTES_MISMATCH",
    "QUARANTINE_MISSING_TEAM_SEASON",
    "QUARANTINE_MISSING_TEAM_TOTALS",
    "QUARANTINE_PLAYED_WITHOUT_SECONDS",
    "QUARANTINE_PLAYER_SUM_MISMATCH",
    "QUARANTINE_SCORE_MISMATCH",
    "QUARANTINE_TEAM_MISMATCH",
    "QUARANTINE_TIED_SCORE",
    "QUARANTINE_UNKNOWN_GAME_TYPE",
    "QUARANTINE_UNKNOWN_PARTICIPATION",
    "QUARANTINE_UNNAMED_PLAYER",
    "QUARANTINE_UNREADABLE_START_TIME",
    "STATUS_FINAL",
    "STORED_GAME_TYPES",
    "WARNING_CUP_FINAL_PLUS_MINUS_ZEROS",
    "WARNING_HOME_CITY_TIED",
    "WARNING_LINE_SCORE_DISAGREES",
    "WARNING_LINE_SCORE_UNREADABLE",
    "WARNING_NEUTRAL_SITE_DEFERRED",
    "GameIssue",
    "GameLineage",
    "GameLoadResult",
    "NeutralSiteResult",
    "check_game",
    "derive_neutral_sites",
    "load_game",
    "neutral_sites",
    "parse_start_time",
    "venue_city",
]
