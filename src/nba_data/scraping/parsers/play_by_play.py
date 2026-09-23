"""Parse a Basketball Reference play-by-play page (`/boxscores/pbp/<game_id>.html`).

The `#pbp` table holds one row per event, in order. A team event has six cells —
clock, visitor event, visitor points, score (visitor-home), home points, home
event — and a game event (period start and end, jump balls) spans the event
columns in one cell. Period boundaries come from the "Start of <n>th
quarter/overtime" events and from the section header rows (`id="q<n>"`); both
name the period absolutely, so they cannot double count.

The clock is never a key: several events share one clock reading, so an event is
identified by its position (`sequence`) within the feed.

Pure: HTML in, typed events out. No network, no database.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from nba_data.validation.team_season import DataQualityIssue

PLAY_BY_PLAY_TABLE_ID = "pbp"
REGULATION_PERIODS = 4
SIDE_VISITOR = "visitor"
SIDE_HOME = "home"
SIDE_GAME = "game"

_PERIOD_START_RE = re.compile(
    r"^Start of (?P<ordinal>[0-9]+)(?:st|nd|rd|th) (?P<kind>quarter|overtime)",
    re.IGNORECASE,
)
_SECTION_ID_RE = re.compile(r"^q(?P<period>[0-9]+)$")
_CLOCK_RE = re.compile(r"^(?P<minutes>[0-9]{1,2}):(?P<seconds>[0-5][0-9])(?:\.(?P<tenths>[0-9]))?$")
_SCORE_RE = re.compile(r"^(?P<visitor>[0-9]+)-(?P<home>[0-9]+)$")
_POINTS_RE = re.compile(r"^\+(?P<points>[1-3])$")
_PLAYER_HREF_RE = re.compile(r"^/players/[a-z]/(?P<player_id>[a-z0-9]+)\.html$")


@dataclass(frozen=True)
class PlayByPlayEvent:
    sequence: int
    period: int
    clock: str
    seconds_remaining: float | None
    side: str
    description: str
    points: int = 0
    visitor_score: int | None = None
    home_score: int | None = None
    player_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedPlayByPlay:
    events: tuple[PlayByPlayEvent, ...]
    issues: tuple[DataQualityIssue, ...]

    @property
    def periods(self) -> int:
        return max((event.period for event in self.events), default=0)

    @property
    def final_score(self) -> tuple[int, int] | None:
        for event in reversed(self.events):
            if event.visitor_score is not None and event.home_score is not None:
                return event.visitor_score, event.home_score
        return None

    def points_by_period(self) -> dict[int, tuple[int, int]]:
        """Visitor and home points scored in each period, from the score column."""

        by_period: dict[int, tuple[int, int]] = {}
        previous = (0, 0)
        for event in self.events:
            if event.visitor_score is None or event.home_score is None:
                continue
            visitor, home = by_period.get(event.period, (0, 0))
            by_period[event.period] = (
                visitor + event.visitor_score - previous[0],
                home + event.home_score - previous[1],
            )
            previous = (event.visitor_score, event.home_score)
        return by_period


def parse_play_by_play_page(html: str) -> ParsedPlayByPlay:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id=PLAY_BY_PLAY_TABLE_ID)
    if not isinstance(table, Tag):
        issue = _issue("play_by_play_table_missing", "no #pbp table was found")
        return ParsedPlayByPlay(events=(), issues=(issue,))

    events: list[PlayByPlayEvent] = []
    issues: list[DataQualityIssue] = []
    period = 0
    for row in table.find_all("tr"):
        section = _SECTION_ID_RE.fullmatch(str(row.get("id", "")))
        if section is not None:
            period = int(section.group("period"))
            continue
        if "thead" in row.get_attribute_list("class"):
            continue

        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        clock = cells[0].get_text(strip=True)
        if _CLOCK_RE.fullmatch(clock) is None:
            continue

        if len(cells) == 2:
            description = _text(cells[1])
            start = _PERIOD_START_RE.match(description)
            if start is not None:
                ordinal = int(start.group("ordinal"))
                is_overtime = start.group("kind").lower() == "overtime"
                period = REGULATION_PERIODS + ordinal if is_overtime else ordinal
            event = PlayByPlayEvent(
                sequence=len(events) + 1,
                period=period,
                clock=clock,
                seconds_remaining=_seconds_remaining(clock),
                side=SIDE_GAME,
                description=description,
                player_ids=_player_ids(cells[1]),
            )
        elif len(cells) == 6:
            parsed = _team_event(cells, sequence=len(events) + 1, period=period, clock=clock)
            if parsed is None:
                issues.append(
                    _issue("event_row_unreadable", f"an event row at {clock} names no side")
                )
                continue
            event = parsed
        else:
            issues.append(
                _issue("event_row_shape", f"an event row at {clock} has {len(cells)} cells")
            )
            continue

        if event.period < 1:
            issues.append(_issue("event_before_first_period", f"an event at {clock} has no period"))
        events.append(event)

    return ParsedPlayByPlay(events=tuple(events), issues=tuple(issues))


def _team_event(
    cells: list[Tag],
    *,
    sequence: int,
    period: int,
    clock: str,
) -> PlayByPlayEvent | None:
    visitor_text = _text(cells[1])
    home_text = _text(cells[5])
    if visitor_text and not home_text:
        side, description, event_cell, points_cell = SIDE_VISITOR, visitor_text, cells[1], cells[2]
    elif home_text and not visitor_text:
        side, description, event_cell, points_cell = SIDE_HOME, home_text, cells[5], cells[4]
    else:
        return None

    points_match = _POINTS_RE.fullmatch(_text(points_cell))
    score_match = _SCORE_RE.fullmatch(_text(cells[3]))
    return PlayByPlayEvent(
        sequence=sequence,
        period=period,
        clock=clock,
        seconds_remaining=_seconds_remaining(clock),
        side=side,
        description=description,
        points=int(points_match.group("points")) if points_match is not None else 0,
        visitor_score=int(score_match.group("visitor")) if score_match is not None else None,
        home_score=int(score_match.group("home")) if score_match is not None else None,
        player_ids=_player_ids(event_cell),
    )


def _player_ids(cell: Tag) -> tuple[str, ...]:
    ids: list[str] = []
    for link in cell.find_all("a", href=True):
        match = _PLAYER_HREF_RE.fullmatch(str(link["href"]))
        if match is not None:
            ids.append(match.group("player_id"))
    return tuple(ids)


def _seconds_remaining(clock: str) -> float | None:
    match = _CLOCK_RE.fullmatch(clock)
    if match is None:
        return None
    tenths = int(match.group("tenths") or 0)
    return int(match.group("minutes")) * 60 + int(match.group("seconds")) + tenths / 10


def _text(cell: Tag) -> str:
    return cell.get_text(" ", strip=True).replace("\xa0", " ").strip()


def _issue(code: str, message: str) -> DataQualityIssue:
    return DataQualityIssue(code=code, message=message, source_table=PLAY_BY_PLAY_TABLE_ID)


__all__ = [
    "REGULATION_PERIODS",
    "SIDE_GAME",
    "SIDE_HOME",
    "SIDE_VISITOR",
    "ParsedPlayByPlay",
    "PlayByPlayEvent",
    "parse_play_by_play_page",
]
