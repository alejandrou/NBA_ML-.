"""Parse a Basketball Reference league schedule page.

`/leagues/NBA_<season_end_year>_games[-<month>].html` lists one month of games
in the `#schedule` table, one row per game. A played game links its box score,
whose id is the stable game key; an unplayed game has no link and no points.

What a row does not say matters as much. Playoff games carry no marker at all —
no separator row, no note — so a row is never classified as regular season
here; the box score heading does that (`parsers/box_score.py`). Play-in games
are the one type the page marks, with the note "Play-In Game". Games abroad are
noted ("at Paris, France") only in some seasons, and the 2020 bubble not at
all. Blank attendance and attendance 0 are different values. Postponed games
that were never played are not listed. (Observed on the 24 pages of the F8-001
pilot.)

Pure: HTML in, typed rows out. No network, no database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from bs4 import BeautifulSoup, Tag

from nba_data.validation.team_season import DataQualityIssue

SCHEDULE_TABLE_ID = "schedule"
PLAY_IN_NOTE = "Play-In Game"

_TEAM_HREF_RE = re.compile(r"^/teams/(?P<code>[A-Z]{3})/(?P<year>[0-9]{4})\.html$")
_BOX_SCORE_HREF_RE = re.compile(r"^/boxscores/(?P<game_id>[0-9]{8}0[A-Z]{3})\.html$")
_MONTH_HREF_RE = re.compile(
    r"^/leagues/NBA_(?P<year>[0-9]{4})_games-(?P<month>[a-z]+(?:-[0-9]{4})?)\.html$"
)
_OVERTIME_RE = re.compile(r"^(?P<count>[1-9][0-9]*)?OT$")
_DATE_CSK_RE = re.compile(r"^(?P<date>[0-9]{8})")


@dataclass(frozen=True)
class ScheduleGame:
    """One schedule row, as published."""

    game_date: date
    visitor_code: str
    visitor_name: str
    home_code: str
    home_name: str
    game_id: str | None = None
    visitor_points: int | None = None
    home_points: int | None = None
    overtime_periods: int = 0
    start_time: str | None = None
    attendance: int | None = None
    game_duration: str | None = None
    arena: str | None = None
    notes: str | None = None

    @property
    def play_in(self) -> bool:
        return self.notes == PLAY_IN_NOTE

    @property
    def played(self) -> bool:
        return (
            self.game_id is not None
            and self.visitor_points is not None
            and self.home_points is not None
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "game_date": self.game_date.isoformat(),
            "play_in": self.play_in,
            "visitor_code": self.visitor_code,
            "visitor_name": self.visitor_name,
            "visitor_points": self.visitor_points,
            "home_code": self.home_code,
            "home_name": self.home_name,
            "home_points": self.home_points,
            "overtime_periods": self.overtime_periods,
            "start_time": self.start_time,
            "attendance": self.attendance,
            "game_duration": self.game_duration,
            "arena": self.arena,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ParsedLeagueSchedule:
    games: tuple[ScheduleGame, ...]
    month_links: tuple[str, ...]
    issues: tuple[DataQualityIssue, ...]


def parse_league_schedule_page(html: str) -> ParsedLeagueSchedule:
    """Parse the schedule rows and month links of one league schedule page."""

    soup = BeautifulSoup(html, "lxml")
    month_links = _month_links(soup)
    table = soup.find("table", id=SCHEDULE_TABLE_ID)
    if not isinstance(table, Tag):
        issue = _issue("schedule_table_missing", "no #schedule table was found")
        return ParsedLeagueSchedule(games=(), month_links=month_links, issues=(issue,))

    body = table.find("tbody")
    rows = body.find_all("tr", recursive=False) if isinstance(body, Tag) else []
    games: list[ScheduleGame] = []
    issues: list[DataQualityIssue] = []

    for index, row in enumerate(rows):
        cells = _cells_by_stat(row)
        if "visitor_team_name" not in cells or "thead" in row.get_attribute_list("class"):
            continue
        game, row_issues = _parse_game_row(cells, index=index)
        issues.extend(row_issues)
        if game is not None:
            games.append(game)

    return ParsedLeagueSchedule(games=tuple(games), month_links=month_links, issues=tuple(issues))


def _parse_game_row(
    cells: dict[str, Tag],
    *,
    index: int,
) -> tuple[ScheduleGame | None, list[DataQualityIssue]]:
    issues: list[DataQualityIssue] = []
    game_date = _game_date(cells.get("date_game"))
    visitor = _team(cells.get("visitor_team_name"))
    home = _team(cells.get("home_team_name"))
    if game_date is None or visitor is None or home is None:
        issues.append(
            _issue(
                "schedule_row_unreadable",
                "a schedule row has no parseable date or team link",
                row_index=index,
            )
        )
        return None, issues

    game_id = _box_score_game_id(cells.get("box_score_text"))
    if game_id is not None and (
        game_id[:8] != game_date.strftime("%Y%m%d") or game_id[-3:] != home[0]
    ):
        issues.append(
            _issue(
                "schedule_game_id_mismatch",
                f"box score id {game_id} disagrees with the row's date or home team",
                row_index=index,
            )
        )

    overtime_text = _text(cells.get("overtimes"))
    overtime_periods = _overtime_periods(overtime_text)
    if overtime_periods is None:
        issues.append(
            _issue(
                "schedule_overtime_unreadable",
                f"overtime marker {overtime_text!r} is not recognized",
                row_index=index,
            )
        )
        overtime_periods = 0

    game = ScheduleGame(
        game_date=game_date,
        visitor_code=visitor[0],
        visitor_name=visitor[1],
        home_code=home[0],
        home_name=home[1],
        game_id=game_id,
        visitor_points=_int(cells.get("visitor_pts")),
        home_points=_int(cells.get("home_pts")),
        overtime_periods=overtime_periods,
        start_time=_text(cells.get("game_start_time")) or None,
        attendance=_int(cells.get("attendance")),
        game_duration=_text(cells.get("game_duration")) or None,
        arena=_text(cells.get("arena_name")) or None,
        notes=_text(cells.get("game_remarks")) or None,
    )
    return game, issues


def _cells_by_stat(row: Tag) -> dict[str, Tag]:
    cells: dict[str, Tag] = {}
    for cell in row.find_all(["th", "td"], recursive=False):
        stat = cell.get("data-stat")
        if isinstance(stat, str) and stat:
            cells[stat] = cell
    return cells


def _game_date(cell: Tag | None) -> date | None:
    if cell is None:
        return None
    text = cell.get_text(" ", strip=True)
    try:
        return datetime.strptime(text, "%a, %b %d, %Y").date()
    except ValueError:
        pass
    csk = cell.get("csk")
    match = _DATE_CSK_RE.match(csk) if isinstance(csk, str) else None
    if match is None:
        return None
    try:
        return datetime.strptime(match.group("date"), "%Y%m%d").date()
    except ValueError:
        return None


def _team(cell: Tag | None) -> tuple[str, str] | None:
    if cell is None:
        return None
    link = cell.find("a", href=True)
    if not isinstance(link, Tag):
        return None
    match = _TEAM_HREF_RE.fullmatch(str(link["href"]))
    if match is None:
        return None
    return match.group("code"), link.get_text(" ", strip=True)


def _box_score_game_id(cell: Tag | None) -> str | None:
    if cell is None:
        return None
    for link in cell.find_all("a", href=True):
        match = _BOX_SCORE_HREF_RE.fullmatch(str(link["href"]))
        if match is not None:
            return match.group("game_id")
    return None


def _overtime_periods(text: str) -> int | None:
    if not text:
        return 0
    match = _OVERTIME_RE.fullmatch(text.upper())
    if match is None:
        return None
    return int(match.group("count") or 1)


def _month_links(soup: BeautifulSoup) -> tuple[str, ...]:
    months: dict[str, None] = {}
    for link in soup.find_all("a", href=True):
        match = _MONTH_HREF_RE.fullmatch(str(link["href"]))
        if match is not None:
            months.setdefault(match.group("month"), None)
    return tuple(months)


def _text(cell: Tag | None) -> str:
    if cell is None:
        return ""
    return cell.get_text(" ", strip=True).replace("\xa0", " ").strip()


def _int(cell: Tag | None) -> int | None:
    text = _text(cell).replace(",", "")
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _issue(code: str, message: str, *, row_index: int | None = None) -> DataQualityIssue:
    return DataQualityIssue(
        code=code,
        message=message,
        row_index=row_index,
        source_table=SCHEDULE_TABLE_ID,
    )


__all__ = [
    "PLAY_IN_NOTE",
    "ParsedLeagueSchedule",
    "ScheduleGame",
    "parse_league_schedule_page",
]
