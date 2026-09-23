"""Parse a Basketball Reference box score page (`/boxscores/<game_id>.html`).

What the pilot needs from it:

* the heading, which is the only place a page says what kind of game it was —
  a plain "<Visitor> at <Home> Box Score, <date>" for the regular season, else
  a prefix: "Play-In Game:", "<year> NBA <round> Game <n>:" for the playoffs, or
  "In-Season Tournament Final:" / "NBA Cup Final:" for the one tournament game
  that does not count toward the regular season. League schedule pages mark
  none of these except play-in games (F8-001 pilot);
* the scorebox — both teams, visitor first, with their final points — and its
  venue line ("Accor Arena, Paris, France"). No page flags a neutral site;
* the line score — points per period, overtime included (the table ships inside
  an HTML comment, as several Basketball Reference tables do);
* each team's full-game basic box, `#box-<CODE>-game-basic` — one line per
  listed player, starters before the "Reserves" separator, and the team totals
  row in the footer;
* the inactive list, which names players who have no line at all.

A listed player without a stat line carries a reason ("Did Not Play", "Did Not
Dress", ...). Participation keeps that apart from a player who played and
recorded zeros — the distinction `docs/ml/PREDICTOR_PLAN.md` requires.

Pure: HTML in, typed values out. No network, no database.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from bs4 import BeautifulSoup, Comment, Tag

from nba_data.validation.team_season import DataQualityIssue

LINE_SCORE_TABLE_ID = "line_score"
BASIC_BOX_TABLE_ID_RE = re.compile(r"^box-(?P<code>[A-Z]{3})-game-basic$")

PARTICIPATION_PLAYED = "played"
PARTICIPATION_DID_NOT_PLAY = "did_not_play"
PARTICIPATION_DID_NOT_DRESS = "did_not_dress"
PARTICIPATION_NOT_WITH_TEAM = "not_with_team"
PARTICIPATION_SUSPENDED = "suspended"
PARTICIPATION_OTHER_ABSENCE = "other_absence"
PARTICIPATION_INACTIVE = "inactive"

GAME_TYPE_REGULAR_SEASON = "regular_season"
GAME_TYPE_PLAY_IN = "play_in"
GAME_TYPE_PLAYOFFS = "playoffs"
GAME_TYPE_CUP_FINAL = "cup_final"
GAME_TYPE_UNKNOWN = "unknown"

_REASON_PARTICIPATION = MappingProxyType(
    {
        "did not play": PARTICIPATION_DID_NOT_PLAY,
        "did not dress": PARTICIPATION_DID_NOT_DRESS,
        "not with team": PARTICIPATION_NOT_WITH_TEAM,
        "player suspended": PARTICIPATION_SUSPENDED,
        "suspended": PARTICIPATION_SUSPENDED,
    }
)

COUNTING_STATS = (
    "fg",
    "fga",
    "fg3",
    "fg3a",
    "ft",
    "fta",
    "orb",
    "drb",
    "trb",
    "ast",
    "stl",
    "blk",
    "tov",
    "pf",
    "pts",
)

_PLAYER_HREF_RE = re.compile(r"^/players/[a-z]/(?P<player_id>[a-z0-9]+)\.html$")
_TEAM_HREF_RE = re.compile(r"^/teams/(?P<code>[A-Z]{3})/(?P<year>[0-9]{4})\.html$")
_MINUTES_RE = re.compile(r"^(?P<minutes>[0-9]+)(?::(?P<seconds>[0-5][0-9]))?$")
_TEAM_CODE_RE = re.compile(r"^[A-Z]{3}$")
_ATTENDANCE_RE = re.compile(r"Attendance:\s*(?P<value>[0-9][0-9,]*)")
_PLAYOFF_LABEL_RE = re.compile(r"^[0-9]{4} NBA .+ Game [0-9]+$")
_CUP_FINAL_LABELS = frozenset({"In-Season Tournament Final", "NBA Cup Final"})
_META_DATE_RE = re.compile(
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r" [0-9]{1,2}, [0-9]{4}$"
)


@dataclass(frozen=True)
class BoxScorePlayerLine:
    player_id: str
    name: str
    starter: bool
    participation: str
    reason: str | None = None
    seconds_played: int | None = None
    stats: Mapping[str, int | None] = field(default_factory=dict)
    plus_minus: int | None = None


@dataclass(frozen=True)
class BoxScoreTeam:
    code: str
    name: str
    scorebox_points: int | None
    line_score: tuple[int, ...] = ()
    line_score_total: int | None = None
    totals_seconds: int | None = None
    totals: Mapping[str, int | None] = field(default_factory=dict)
    players: tuple[BoxScorePlayerLine, ...] = ()
    inactive_player_ids: tuple[str, ...] = ()

    @property
    def played_lines(self) -> tuple[BoxScorePlayerLine, ...]:
        return tuple(line for line in self.players if line.participation == PARTICIPATION_PLAYED)


@dataclass(frozen=True)
class ParsedBoxScore:
    visitor: BoxScoreTeam | None
    home: BoxScoreTeam | None
    period_labels: tuple[str, ...]
    scorebox_meta: tuple[str, ...]
    attendance: int | None
    play_by_play_linked: bool
    issues: tuple[DataQualityIssue, ...]
    heading: str | None = None
    game_label: str | None = None
    game_type: str = GAME_TYPE_UNKNOWN
    venue: str | None = None

    @property
    def teams(self) -> tuple[BoxScoreTeam, ...]:
        return tuple(team for team in (self.visitor, self.home) if team is not None)


def parse_box_score_page(html: str) -> ParsedBoxScore:
    soup = _soup_with_commented_markup(html)
    issues: list[DataQualityIssue] = []
    heading = _heading(soup)
    game_label, game_type = _game_type(heading, issues)
    scorebox_meta = _scorebox_meta(soup)
    venue = _venue(scorebox_meta)

    scorebox_teams = _scorebox_teams(soup)
    if len(scorebox_teams) != 2:
        issues.append(
            _issue(
                "scorebox_teams_unreadable",
                f"expected two scorebox teams, found {len(scorebox_teams)}",
                "scorebox",
            )
        )
        return ParsedBoxScore(
            visitor=None,
            home=None,
            period_labels=(),
            scorebox_meta=scorebox_meta,
            attendance=_attendance(soup),
            play_by_play_linked=_play_by_play_linked(soup),
            issues=tuple(issues),
            heading=heading,
            game_label=game_label,
            game_type=game_type,
            venue=venue,
        )

    period_labels, line_scores = _line_score(soup, issues)
    inactive = _inactive_players(soup)
    teams: list[BoxScoreTeam] = []
    for code, name, points in scorebox_teams:
        per_period = line_scores.get(code, ())
        totals_seconds, totals, players = _basic_box(soup, code, issues)
        teams.append(
            BoxScoreTeam(
                code=code,
                name=name,
                scorebox_points=points,
                line_score=per_period[:-1] if per_period else (),
                line_score_total=per_period[-1] if per_period else None,
                totals_seconds=totals_seconds,
                totals=totals,
                players=players,
                inactive_player_ids=inactive.get(code, ()),
            )
        )

    return ParsedBoxScore(
        visitor=teams[0],
        home=teams[1],
        period_labels=period_labels,
        scorebox_meta=scorebox_meta,
        attendance=_attendance(soup),
        play_by_play_linked=_play_by_play_linked(soup),
        issues=tuple(issues),
        heading=heading,
        game_label=game_label,
        game_type=game_type,
        venue=venue,
    )


def _venue(scorebox_meta: tuple[str, ...]) -> str | None:
    """The line after the date line; tournament games put a label before the date."""

    for index, line in enumerate(scorebox_meta[:-1]):
        if _META_DATE_RE.search(line):
            following = scorebox_meta[index + 1]
            return None if following.startswith("Logos via") else following
    return None


def _heading(soup: BeautifulSoup) -> str | None:
    h1 = soup.find("h1")
    if not isinstance(h1, Tag):
        return None
    return h1.get_text(" ", strip=True) or None


def _game_type(
    heading: str | None,
    issues: list[DataQualityIssue],
) -> tuple[str | None, str]:
    """Return the heading's label prefix, if any, and the game type it names."""

    if heading is None:
        issues.append(_issue("heading_missing", "no <h1> heading was found", "heading"))
        return None, GAME_TYPE_UNKNOWN
    if ":" not in heading:
        return None, GAME_TYPE_REGULAR_SEASON

    label = heading.split(":", maxsplit=1)[0].strip()
    if label == "Play-In Game":
        return label, GAME_TYPE_PLAY_IN
    if label in _CUP_FINAL_LABELS:
        return label, GAME_TYPE_CUP_FINAL
    if _PLAYOFF_LABEL_RE.fullmatch(label):
        return label, GAME_TYPE_PLAYOFFS
    issues.append(
        _issue(
            "game_type_unrecognized", f"heading label {label!r} names no known game type", "heading"
        )
    )
    return label, GAME_TYPE_UNKNOWN


def _soup_with_commented_markup(html: str) -> BeautifulSoup:
    """Parse the page, then append markup Basketball Reference ships in comments."""

    soup = BeautifulSoup(html, "lxml")
    body = soup.body if soup.body is not None else soup
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        if "<table" not in comment and "Inactive" not in comment:
            continue
        fragment = BeautifulSoup(str(comment), "lxml")
        container = fragment.body if fragment.body is not None else fragment
        for child in list(container.children):
            if isinstance(child, Tag):
                body.append(child)
    return soup


def _scorebox_teams(soup: BeautifulSoup) -> list[tuple[str, str, int | None]]:
    scorebox = soup.find("div", class_="scorebox")
    if not isinstance(scorebox, Tag):
        return []
    teams: list[tuple[str, str, int | None]] = []
    for block in scorebox.find_all("div", recursive=False):
        link = None
        for candidate in block.find_all("a", href=True):
            if _TEAM_HREF_RE.fullmatch(str(candidate["href"])):
                link = candidate
                break
        if link is None:
            continue
        match = _TEAM_HREF_RE.fullmatch(str(link["href"]))
        assert match is not None
        score = block.find("div", class_="score")
        teams.append(
            (
                match.group("code"),
                link.get_text(" ", strip=True),
                _to_int(score.get_text(strip=True)) if isinstance(score, Tag) else None,
            )
        )
    return teams


def _scorebox_meta(soup: BeautifulSoup) -> tuple[str, ...]:
    meta = soup.find("div", class_="scorebox_meta")
    if not isinstance(meta, Tag):
        return ()
    return tuple(
        text
        for block in meta.find_all("div", recursive=False)
        if (text := block.get_text(" ", strip=True))
    )


def _line_score(
    soup: BeautifulSoup,
    issues: list[DataQualityIssue],
) -> tuple[tuple[str, ...], dict[str, tuple[int, ...]]]:
    table = soup.find("table", id=LINE_SCORE_TABLE_ID)
    if not isinstance(table, Tag):
        issues.append(_issue("line_score_missing", "no #line_score table", LINE_SCORE_TABLE_ID))
        return (), {}

    head = table.find("thead")
    header_rows = head.find_all("tr") if isinstance(head, Tag) else []
    labels: tuple[str, ...] = ()
    if header_rows:
        cells = header_rows[-1].find_all(["th", "td"], recursive=False)
        labels = tuple(cell.get_text(strip=True) for cell in cells[1:-1])

    scores: dict[str, tuple[int, ...]] = {}
    body = table.find("tbody")
    rows = body.find_all("tr", recursive=False) if isinstance(body, Tag) else []
    for row in rows:
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) < 3:
            continue
        code = _line_score_team_code(cells[0])
        values = [_to_int(cell.get_text(strip=True)) for cell in cells[1:]]
        if code is None or any(value is None for value in values):
            issues.append(
                _issue("line_score_row_unreadable", "a line score row is unreadable", "line_score")
            )
            continue
        scores[code] = tuple(value for value in values if value is not None)

    if labels and any(len(values) != len(labels) + 1 for values in scores.values()):
        issues.append(
            _issue(
                "line_score_shape",
                "a line score row does not have one value per period plus a total",
                LINE_SCORE_TABLE_ID,
            )
        )
    return labels, scores


def _line_score_team_code(cell: Tag) -> str | None:
    link = cell.find("a", href=True)
    if isinstance(link, Tag):
        match = _TEAM_HREF_RE.fullmatch(str(link["href"]))
        if match is not None:
            return match.group("code")
    text = cell.get_text(strip=True).upper()
    return text if _TEAM_CODE_RE.fullmatch(text) else None


def _basic_box(
    soup: BeautifulSoup,
    code: str,
    issues: list[DataQualityIssue],
) -> tuple[int | None, dict[str, int | None], tuple[BoxScorePlayerLine, ...]]:
    table_id = f"box-{code}-game-basic"
    table = soup.find("table", id=table_id)
    if not isinstance(table, Tag):
        issues.append(_issue("basic_box_missing", f"no #{table_id} table", table_id))
        return None, {}, ()

    players: list[BoxScorePlayerLine] = []
    body = table.find("tbody")
    rows = body.find_all("tr", recursive=False) if isinstance(body, Tag) else []
    starter = True
    for row in rows:
        if "thead" in row.get_attribute_list("class"):
            starter = False
            continue
        line = _player_line(row, starter=starter)
        if line is None:
            issues.append(
                _issue("player_row_unreadable", "a box score row has no player link", table_id)
            )
            continue
        players.append(line)

    totals_seconds: int | None = None
    totals: dict[str, int | None] = {}
    footer = table.find("tfoot")
    total_row = footer.find("tr") if isinstance(footer, Tag) else None
    if isinstance(total_row, Tag):
        cells = _cells_by_stat(total_row)
        minutes = _to_int(_cell_text(cells.get("mp")))
        totals_seconds = minutes * 60 if minutes is not None else None
        totals = {stat: _to_int(_cell_text(cells.get(stat))) for stat in COUNTING_STATS}
    else:
        issues.append(_issue("team_totals_missing", f"#{table_id} has no totals row", table_id))

    return totals_seconds, totals, tuple(players)


def _player_line(row: Tag, *, starter: bool) -> BoxScorePlayerLine | None:
    cells = _cells_by_stat(row)
    player_cell = cells.get("player")
    if player_cell is None:
        return None
    player_id = _player_id(player_cell)
    if player_id is None:
        return None
    name = player_cell.get_text(" ", strip=True)

    reason_cell = cells.get("reason")
    if reason_cell is not None:
        reason = reason_cell.get_text(" ", strip=True)
        return BoxScorePlayerLine(
            player_id=player_id,
            name=name,
            starter=starter,
            participation=_REASON_PARTICIPATION.get(reason.lower(), PARTICIPATION_OTHER_ABSENCE),
            reason=reason,
        )

    return BoxScorePlayerLine(
        player_id=player_id,
        name=name,
        starter=starter,
        participation=PARTICIPATION_PLAYED,
        seconds_played=_seconds(_cell_text(cells.get("mp"))),
        stats={stat: _to_int(_cell_text(cells.get(stat))) for stat in COUNTING_STATS},
        plus_minus=_to_int(_cell_text(cells.get("plus_minus"))),
    )


def _player_id(cell: Tag) -> str | None:
    appended = cell.get("data-append-csv")
    if isinstance(appended, str) and appended:
        return appended
    link = cell.find("a", href=True)
    if not isinstance(link, Tag):
        return None
    match = _PLAYER_HREF_RE.fullmatch(str(link["href"]))
    return match.group("player_id") if match is not None else None


def _inactive_players(soup: BeautifulSoup) -> dict[str, tuple[str, ...]]:
    """Map team code to the player ids listed after "Inactive:"."""

    label = soup.find(
        lambda tag: tag.name == "strong" and tag.get_text(strip=True).startswith("Inactive")
    )
    if not isinstance(label, Tag) or not isinstance(label.parent, Tag):
        return {}

    inactive: dict[str, list[str]] = {}
    current: str | None = None
    for node in label.parent.descendants:
        if not isinstance(node, Tag):
            continue
        if node.name == "strong" and node is not label:
            text = node.get_text(strip=True).replace("\xa0", "").upper()
            if _TEAM_CODE_RE.fullmatch(text):
                current = text
        elif node.name == "a" and current is not None:
            match = _PLAYER_HREF_RE.fullmatch(str(node.get("href", "")))
            if match is not None:
                inactive.setdefault(current, []).append(match.group("player_id"))
    return {code: tuple(ids) for code, ids in inactive.items()}


def _attendance(soup: BeautifulSoup) -> int | None:
    match = _ATTENDANCE_RE.search(soup.get_text(" ", strip=True).replace("\xa0", " "))
    return _to_int(match.group("value")) if match is not None else None


def _play_by_play_linked(soup: BeautifulSoup) -> bool:
    return any(
        str(link["href"]).startswith("/boxscores/pbp/") for link in soup.find_all("a", href=True)
    )


def _cells_by_stat(row: Tag) -> dict[str, Tag]:
    cells: dict[str, Tag] = {}
    for cell in row.find_all(["th", "td"], recursive=False):
        stat = cell.get("data-stat")
        if isinstance(stat, str) and stat:
            cells[stat] = cell
    return cells


def _cell_text(cell: Tag | None) -> str:
    return cell.get_text(strip=True) if cell is not None else ""


def _seconds(text: str) -> int | None:
    match = _MINUTES_RE.fullmatch(text)
    if match is None:
        return None
    return int(match.group("minutes")) * 60 + int(match.group("seconds") or 0)


def _to_int(text: str) -> int | None:
    cleaned = text.replace(",", "").replace("\xa0", "").strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _issue(code: str, message: str, source_table: str) -> DataQualityIssue:
    return DataQualityIssue(code=code, message=message, source_table=source_table)


__all__ = [
    "COUNTING_STATS",
    "GAME_TYPE_CUP_FINAL",
    "GAME_TYPE_PLAYOFFS",
    "GAME_TYPE_PLAY_IN",
    "GAME_TYPE_REGULAR_SEASON",
    "GAME_TYPE_UNKNOWN",
    "PARTICIPATION_DID_NOT_DRESS",
    "PARTICIPATION_DID_NOT_PLAY",
    "PARTICIPATION_INACTIVE",
    "PARTICIPATION_NOT_WITH_TEAM",
    "PARTICIPATION_OTHER_ABSENCE",
    "PARTICIPATION_PLAYED",
    "PARTICIPATION_SUSPENDED",
    "BoxScorePlayerLine",
    "BoxScoreTeam",
    "ParsedBoxScore",
    "parse_box_score_page",
]
