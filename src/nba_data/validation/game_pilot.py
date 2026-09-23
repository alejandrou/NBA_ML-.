"""Offline reconciliation for the F8-001 per-game acquisition pilot.

For every game the pilot manifests name, this reads the cached schedule, box
score, and play-by-play pages — never the network, never the database — and
checks that they tell one story:

* the schedule, the scorebox, the team totals, the line score, and the
  play-by-play agree on the teams and the final score;
* the line score has one period per quarter and overtime, and the play-by-play
  scores the same points in each period;
* player lines add up to the team totals, minutes add up to the game length,
  each team lists five starters, and no player appears twice;
* every points-scoring event credits the player the box score credits, and
  every player an event names is on that game's box score;
* the schedule's play-in note agrees with the box score heading;
* every team code and player id resolves to an identity `core` already holds.

The tolerances are properties of the source, measured on the pilot's pages, not
leniency: a team's turnovers include team turnovers (shot-clock and other team
violations) that no player line carries, and each player's minutes are
published rounded to the second, so their sum may miss the game length by up to
half a second per line. A blank cell is never read as zero: summed as one, a
turnover column missing from every player line would pass as team turnovers.

Identity is checked against the cache, which mirrors `core`: the reviewed
team-season catalog (`nba_team_season_manifest.py`) is `core.team_seasons`, and
the cached player pages were acquired from `core.players`. `core.players` holds
players with a roster or stat row, so a player who appears only in a box score's
inactive list — paid, never played for that team that season — may be missing;
that, and any identity from a season past the archive, is an expected gap.

Each check ends `passed`, `failed`, `expected_gap`, or `not_checked` (its input
is legitimately absent at the source, such as play-by-play for a game whose box
score links none). Only `failed` fails a game. The report fails closed: it
fails when the manifests name no game, when a game's box score or linked
play-by-play is not requested, and when a schedule page lists no game — so
leaving a manifest out never reads as a pass.

Alongside the checks, each game records what the play-by-play offers a later
lineup reconstruction: substitutions, same-clock substitution groups, replay
reviews, and how often carrying each period's closing lineup into the next
period contradicts a logged substitution (the pages do not log lineup changes
between periods).
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

from nba_data.domain.player_id import PLAYER_ID_PATTERN
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.game_pilot_manifest import (
    PAGE_TYPE_BOX_SCORE,
    PAGE_TYPE_LEAGUE_SCHEDULE,
    PAGE_TYPE_PLAY_BY_PLAY,
    GamePilotManifest,
    parse_game_id,
)
from nba_data.scraping.parsers.box_score import (
    COUNTING_STATS,
    GAME_TYPE_PLAY_IN,
    BoxScoreTeam,
    ParsedBoxScore,
    parse_box_score_page,
)
from nba_data.scraping.parsers.league_schedule import ScheduleGame, parse_league_schedule_page
from nba_data.scraping.parsers.play_by_play import (
    REGULATION_PERIODS,
    SIDE_HOME,
    SIDE_VISITOR,
    ParsedPlayByPlay,
    parse_play_by_play_page,
)

CHECK_PASSED = "passed"
CHECK_FAILED = "failed"
CHECK_EXPECTED_GAP = "expected_gap"
CHECK_NOT_CHECKED = "not_checked"

REGULATION_TEAM_MINUTES = 240
OVERTIME_TEAM_MINUTES = 25
TEAM_LEVEL_STATS = frozenset({"tov"})
SUBSTITUTION_MARKER = " enters the game for "
REVIEW_MARKER = "Instant Replay"

_PLAYER_CACHE_NAME_RE = re.compile(
    rf"^players-[a-z]-(?P<player_id>{PLAYER_ID_PATTERN})\.html-[0-9a-f]{{16}}\.html\.gz$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class GamePilotCheck:
    code: str
    status: str
    detail: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {"code": self.code, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class PlayByPlayProfile:
    """What the play-by-play offers a later lineup reconstruction."""

    events: int = 0
    substitutions: int = 0
    same_clock_substitution_groups: int = 0
    review_events: int = 0
    lineup_carryover_conflicts: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "events": self.events,
            "substitutions": self.substitutions,
            "same_clock_substitution_groups": self.same_clock_substitution_groups,
            "review_events": self.review_events,
            "lineup_carryover_conflicts": self.lineup_carryover_conflicts,
        }


@dataclass(frozen=True)
class GamePilotGameResult:
    game_id: str
    season_end_year: int
    game_date: str
    selection_reason: str
    visitor_code: str | None
    home_code: str | None
    visitor_points: int | None
    home_points: int | None
    periods: int | None
    game_type: str | None
    game_label: str | None
    venue: str | None
    schedule_notes: str | None
    attendance: int | None
    play_by_play_status: str
    play_by_play: PlayByPlayProfile
    participation: Mapping[str, int]
    inactive_players: int
    team_turnovers: Mapping[str, int | None]
    unresolved_player_ids: tuple[str, ...]
    unresolved_team_codes: tuple[str, ...]
    requests: int | None
    bytes: int
    compressed_bytes: int
    elapsed_seconds: float | None
    checks: tuple[GamePilotCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.status != CHECK_FAILED for check in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "game_id": self.game_id,
            "season_end_year": self.season_end_year,
            "game_date": self.game_date,
            "selection_reason": self.selection_reason,
            "visitor_code": self.visitor_code,
            "home_code": self.home_code,
            "visitor_points": self.visitor_points,
            "home_points": self.home_points,
            "periods": self.periods,
            "game_type": self.game_type,
            "game_label": self.game_label,
            "venue": self.venue,
            "schedule_notes": self.schedule_notes,
            "attendance": self.attendance,
            "play_by_play_status": self.play_by_play_status,
            "play_by_play": self.play_by_play.to_dict(),
            "participation": dict(self.participation),
            "inactive_players": self.inactive_players,
            "team_turnovers": dict(self.team_turnovers),
            "unresolved_player_ids": list(self.unresolved_player_ids),
            "unresolved_team_codes": list(self.unresolved_team_codes),
            "requests": self.requests,
            "bytes": self.bytes,
            "compressed_bytes": self.compressed_bytes,
            "elapsed_seconds": self.elapsed_seconds,
            "passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass(frozen=True)
class GamePilotSchedulePage:
    url: str
    season_end_year: int
    month: str | None
    cached: bool
    games: int
    played_games: int
    play_in_games: int
    issues: tuple[str, ...]
    requests: int | None
    bytes: int
    compressed_bytes: int
    elapsed_seconds: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "url": self.url,
            "season_end_year": self.season_end_year,
            "month": self.month,
            "cached": self.cached,
            "games": self.games,
            "played_games": self.played_games,
            "play_in_games": self.play_in_games,
            "issues": list(self.issues),
            "requests": self.requests,
            "bytes": self.bytes,
            "compressed_bytes": self.compressed_bytes,
            "elapsed_seconds": self.elapsed_seconds,
        }


@dataclass(frozen=True)
class GamePilotValidationReport:
    manifest_ids: tuple[str, ...]
    archive_last_season: int
    schedule_pages: tuple[GamePilotSchedulePage, ...]
    games: tuple[GamePilotGameResult, ...]
    check_totals: Mapping[str, Mapping[str, int]] = field(default_factory=dict)

    @property
    def coverage_problems(self) -> tuple[str, ...]:
        """Why the report cannot pass whatever its checks say: nothing was validated."""

        return () if self.games else ("the manifests name no game",)

    @property
    def passed(self) -> bool:
        return (
            not self.coverage_problems
            and all(game.passed for game in self.games)
            and all(page.cached and not page.issues for page in self.schedule_pages)
        )

    def to_dict(self) -> dict[str, object]:
        requests = [
            value
            for value in [game.requests for game in self.games]
            + [page.requests for page in self.schedule_pages]
            if value is not None
        ]
        elapsed = [
            value
            for value in [game.elapsed_seconds for game in self.games]
            + [page.elapsed_seconds for page in self.schedule_pages]
            if value is not None
        ]
        return {
            "manifest_ids": list(self.manifest_ids),
            "archive_last_season": self.archive_last_season,
            "passed": self.passed,
            "coverage_problems": list(self.coverage_problems),
            "games": len(self.games),
            "games_passed": sum(game.passed for game in self.games),
            "failed_games": [game.game_id for game in self.games if not game.passed],
            "schedule_pages": len(self.schedule_pages),
            "measured_requests": sum(requests),
            "measured_elapsed_seconds": round(sum(elapsed), 3),
            "game_bytes": sum(game.bytes for game in self.games),
            "game_compressed_bytes": sum(game.compressed_bytes for game in self.games),
            "schedule_bytes": sum(page.bytes for page in self.schedule_pages),
            "schedule_compressed_bytes": sum(page.compressed_bytes for page in self.schedule_pages),
            "check_totals": {code: dict(counts) for code, counts in self.check_totals.items()},
            "schedule_page_results": [page.to_dict() for page in self.schedule_pages],
            "game_results": [game.to_dict() for game in self.games],
        }


@dataclass(frozen=True)
class _Measurement:
    requests: int | None
    elapsed_seconds: float | None


def known_player_ids_from_cache(cache_root: str | Path) -> frozenset[str]:
    """Player ids with a cached player page — the ids `core.players` holds."""

    root = Path(cache_root) / "basketball-reference"
    if not root.is_dir():
        return frozenset()
    ids: set[str] = set()
    for path in root.glob("players-*.html.gz"):
        match = _PLAYER_CACHE_NAME_RE.fullmatch(path.name)
        if match is not None:
            ids.add(match.group("player_id").lower())
    return frozenset(ids)


def build_game_pilot_validation_report(
    manifests: Iterable[GamePilotManifest],
    *,
    cache: HtmlCache,
    known_player_ids: frozenset[str],
    known_team_seasons: frozenset[tuple[str, int]],
    archive_last_season: int,
    acquisition_reports: Iterable[Mapping[str, object]] = (),
) -> GamePilotValidationReport:
    manifest_list = list(manifests)
    measurements = _measurements_by_url(acquisition_reports)

    schedule_pages: list[GamePilotSchedulePage] = []
    schedule_games: dict[str, ScheduleGame] = {}
    game_entries: dict[str, dict[str, str]] = {}
    game_seasons: dict[str, int] = {}
    game_reasons: dict[str, str] = {}

    schedule_urls: set[str] = set()

    for manifest in manifest_list:
        for entry in manifest.entries:
            if entry.page_type == PAGE_TYPE_LEAGUE_SCHEDULE:
                if entry.url in schedule_urls:
                    continue
                schedule_urls.add(entry.url)
                page, games = _schedule_page(entry.url, entry.season_end_year, entry.month, cache)
                schedule_pages.append(_with_measurement(page, measurements.get(entry.url)))
                for game in games:
                    if game.game_id is not None:
                        schedule_games.setdefault(game.game_id, game)
            elif entry.game_id is not None:
                game_entries.setdefault(entry.game_id, {})[entry.page_type] = entry.url
                game_seasons[entry.game_id] = entry.season_end_year
                game_reasons.setdefault(entry.game_id, entry.reason)

    results = tuple(
        _game_result(
            game_id,
            urls=urls,
            season_end_year=game_seasons[game_id],
            selection_reason=game_reasons[game_id],
            schedule_game=schedule_games.get(game_id),
            cache=cache,
            measurements=measurements,
            known_player_ids=known_player_ids,
            known_team_seasons=known_team_seasons,
            archive_last_season=archive_last_season,
        )
        for game_id, urls in game_entries.items()
    )

    totals: dict[str, Counter[str]] = {}
    for result in results:
        for check in result.checks:
            totals.setdefault(check.code, Counter())[check.status] += 1

    return GamePilotValidationReport(
        manifest_ids=tuple(manifest.manifest_id for manifest in manifest_list),
        archive_last_season=archive_last_season,
        schedule_pages=tuple(schedule_pages),
        games=results,
        check_totals={code: dict(counter) for code, counter in sorted(totals.items())},
    )


def _schedule_page(
    url: str,
    season_end_year: int,
    month: str | None,
    cache: HtmlCache,
) -> tuple[GamePilotSchedulePage, tuple[ScheduleGame, ...]]:
    html = cache.get(url)
    if html is None:
        page = GamePilotSchedulePage(
            url=url,
            season_end_year=season_end_year,
            month=month,
            cached=False,
            games=0,
            played_games=0,
            play_in_games=0,
            issues=("not_cached",),
            requests=None,
            bytes=0,
            compressed_bytes=0,
            elapsed_seconds=None,
        )
        return page, ()

    parsed = parse_league_schedule_page(html)
    issues = tuple(issue.code for issue in parsed.issues)
    if not parsed.games and not issues:
        issues = ("no_games",)
    page = GamePilotSchedulePage(
        url=url,
        season_end_year=season_end_year,
        month=month,
        cached=True,
        games=len(parsed.games),
        played_games=sum(game.played for game in parsed.games),
        play_in_games=sum(game.play_in for game in parsed.games),
        issues=issues,
        requests=None,
        bytes=len(html.encode("utf-8")),
        compressed_bytes=cache.path_for_url(url).stat().st_size,
        elapsed_seconds=None,
    )
    return page, parsed.games


def _with_measurement(
    page: GamePilotSchedulePage,
    measurement: _Measurement | None,
) -> GamePilotSchedulePage:
    if measurement is None:
        return page
    return replace(
        page,
        requests=measurement.requests,
        elapsed_seconds=measurement.elapsed_seconds,
    )


def _game_result(
    game_id: str,
    *,
    urls: Mapping[str, str],
    season_end_year: int,
    selection_reason: str,
    schedule_game: ScheduleGame | None,
    cache: HtmlCache,
    measurements: Mapping[str, _Measurement],
    known_player_ids: frozenset[str],
    known_team_seasons: frozenset[tuple[str, int]],
    archive_last_season: int,
) -> GamePilotGameResult:
    checks: list[GamePilotCheck] = []
    game_date, home_from_id = parse_game_id(game_id)
    beyond_archive = season_end_year > archive_last_season

    box_url = urls.get(PAGE_TYPE_BOX_SCORE)
    box_html = cache.get(box_url) if box_url is not None else None
    box = parse_box_score_page(box_html) if box_html is not None else None
    if box_url is None:
        checks.append(
            _failed("box_score_requested", "the manifests request no box score for this game")
        )
    elif box is None:
        checks.append(_failed("box_score_cached", "the box score page is not in the cache"))
    elif box.issues:
        checks.append(
            _failed("box_score_parsed", ", ".join(sorted({issue.code for issue in box.issues})))
        )
    else:
        checks.append(GamePilotCheck("box_score_parsed", CHECK_PASSED))

    pbp_url = urls.get(PAGE_TYPE_PLAY_BY_PLAY)
    pbp_html = cache.get(pbp_url) if pbp_url is not None else None
    pbp = parse_play_by_play_page(pbp_html) if pbp_html is not None else None
    if pbp_url is None:
        if box is not None and not box.play_by_play_linked:
            pbp_status = "unavailable"
        else:
            # Linked, or unknowable without the box score: an omission, not a gap.
            pbp_status = "not_in_manifest"
            checks.append(
                _failed(
                    "play_by_play_requested",
                    "the manifests request no play-by-play for this game",
                )
            )
    elif pbp is None:
        pbp_status = "not_cached"
        checks.append(_failed("play_by_play_cached", "the play-by-play page is not in the cache"))
    elif pbp.issues:
        pbp_status = "parsed_with_issues"
        checks.append(
            _failed(
                "play_by_play_parsed",
                ", ".join(sorted({issue.code for issue in pbp.issues})),
            )
        )
    else:
        pbp_status = "parsed"
        checks.append(GamePilotCheck("play_by_play_parsed", CHECK_PASSED))

    visitor = box.visitor if box is not None else None
    home = box.home if box is not None else None
    profile = PlayByPlayProfile(events=len(pbp.events) if pbp is not None else 0)
    unresolved_teams: list[str] = []
    unresolved_players: list[str] = []
    if box is not None and visitor is not None and home is not None:
        checks.extend(_schedule_checks(schedule_game, box, visitor, home, home_from_id))
        checks.extend(_box_score_checks(box, visitor, home, schedule_game))
        if pbp is not None and not pbp.issues:
            checks.extend(_play_by_play_checks(pbp, visitor, home))
            profile = _play_by_play_profile(pbp, visitor, home)
        else:
            checks.append(
                GamePilotCheck(
                    "play_by_play_reconciles",
                    CHECK_NOT_CHECKED,
                    f"play-by-play is {pbp_status}",
                )
            )
        team_check, unresolved_teams = _team_identity_check(
            (visitor.code, home.code), season_end_year, known_team_seasons, beyond_archive
        )
        player_check, unresolved_players = _player_identity_check(
            (visitor, home), known_player_ids, beyond_archive
        )
        checks.extend((team_check, player_check))

    participation: Counter[str] = Counter()
    inactive = 0
    team_turnovers: dict[str, int | None] = {}
    for team in (visitor, home):
        if team is not None:
            participation.update(line.participation for line in team.players)
            inactive += len(team.inactive_player_ids)
            team_turnovers[team.code] = _team_only_amount(team, "tov")

    game_urls = [url for url in (box_url, pbp_url) if url is not None]
    game_measurements = [measurements[url] for url in game_urls if url in measurements]
    requests = [m.requests for m in game_measurements if m.requests is not None]
    elapsed = [m.elapsed_seconds for m in game_measurements if m.elapsed_seconds is not None]
    html_pages = [html for html in (box_html, pbp_html) if html is not None]

    return GamePilotGameResult(
        game_id=game_id,
        season_end_year=season_end_year,
        game_date=game_date.isoformat(),
        selection_reason=selection_reason,
        visitor_code=visitor.code if visitor is not None else None,
        home_code=home.code if home is not None else None,
        visitor_points=visitor.scorebox_points if visitor is not None else None,
        home_points=home.scorebox_points if home is not None else None,
        periods=len(box.period_labels) if box is not None and box.period_labels else None,
        game_type=box.game_type if box is not None else None,
        game_label=box.game_label if box is not None else None,
        venue=box.venue if box is not None else None,
        schedule_notes=schedule_game.notes if schedule_game is not None else None,
        attendance=(
            box.attendance
            if box is not None and box.attendance is not None
            else (schedule_game.attendance if schedule_game is not None else None)
        ),
        play_by_play_status=pbp_status,
        play_by_play=profile,
        participation=dict(sorted(participation.items())),
        inactive_players=inactive,
        team_turnovers=team_turnovers,
        unresolved_player_ids=tuple(unresolved_players),
        unresolved_team_codes=tuple(unresolved_teams),
        requests=sum(requests) if requests else None,
        bytes=sum(len(html.encode("utf-8")) for html in html_pages),
        compressed_bytes=sum(
            cache.path_for_url(url).stat().st_size for url in game_urls if cache.exists(url)
        ),
        elapsed_seconds=round(sum(elapsed), 3) if elapsed else None,
        checks=tuple(checks),
    )


def _schedule_checks(
    schedule_game: ScheduleGame | None,
    box: ParsedBoxScore,
    visitor: BoxScoreTeam,
    home: BoxScoreTeam,
    home_from_id: str,
) -> list[GamePilotCheck]:
    checks: list[GamePilotCheck] = []
    if home.code != home_from_id:
        checks.append(
            _failed("game_id_home_team", f"the id names {home_from_id}, the box score {home.code}")
        )
    if schedule_game is None:
        checks.append(_failed("schedule_row", "no cached schedule page lists this game"))
        return checks

    checks.append(GamePilotCheck("schedule_row", CHECK_PASSED))
    schedule_teams = (schedule_game.visitor_code, schedule_game.home_code)
    checks.append(
        GamePilotCheck("teams_agree", CHECK_PASSED)
        if schedule_teams == (visitor.code, home.code)
        else _failed(
            "teams_agree",
            f"schedule {schedule_teams} vs box score {(visitor.code, home.code)}",
        )
    )
    box_play_in = box.game_type == GAME_TYPE_PLAY_IN
    checks.append(
        GamePilotCheck("play_in_marked_consistently", CHECK_PASSED)
        if schedule_game.play_in == box_play_in
        else _failed(
            "play_in_marked_consistently",
            f"schedule play-in {schedule_game.play_in}, box score heading {box.game_label!r}",
        )
    )
    return checks


def _box_score_checks(
    box: ParsedBoxScore,
    visitor: BoxScoreTeam,
    home: BoxScoreTeam,
    schedule_game: ScheduleGame | None,
) -> list[GamePilotCheck]:
    checks: list[GamePilotCheck] = []

    scores = {
        "scorebox": (visitor.scorebox_points, home.scorebox_points),
        "team_totals": (visitor.totals.get("pts"), home.totals.get("pts")),
        "line_score": (visitor.line_score_total, home.line_score_total),
        "line_score_sum": (
            sum(visitor.line_score) if visitor.line_score else None,
            sum(home.line_score) if home.line_score else None,
        ),
    }
    if schedule_game is not None:
        scores["schedule"] = (schedule_game.visitor_points, schedule_game.home_points)
    distinct = set(scores.values())
    if len(distinct) == 1 and None not in next(iter(distinct)):
        checks.append(GamePilotCheck("final_score_agrees", CHECK_PASSED))
    else:
        detail = "; ".join(f"{source} {value}" for source, value in scores.items())
        checks.append(_failed("final_score_agrees", detail))

    periods = len(visitor.line_score)
    expected = (
        REGULATION_PERIODS + schedule_game.overtime_periods if schedule_game is not None else None
    )
    if periods != len(home.line_score) or periods != len(box.period_labels):
        checks.append(_failed("line_score_periods", "line score rows disagree in length"))
    elif expected is not None and periods != expected:
        checks.append(
            _failed("line_score_periods", f"{periods} periods, schedule implies {expected}")
        )
    elif periods < REGULATION_PERIODS:
        checks.append(_failed("line_score_periods", f"only {periods} periods"))
    else:
        checks.append(GamePilotCheck("line_score_periods", CHECK_PASSED))

    overtime_periods = max(periods - REGULATION_PERIODS, 0)
    checks.append(_per_team("player_sums_match_totals", (visitor, home), _totals_problem))
    checks.append(
        _per_team(
            "minutes_match_game_length",
            (visitor, home),
            lambda team: _minutes_problem(team, overtime_periods),
        )
    )
    checks.append(
        _per_team(
            "five_starters",
            (visitor, home),
            lambda team: (
                None
                if (starters := sum(line.starter for line in team.players)) == 5
                else f"{starters} starters listed"
            ),
        )
    )

    listed = [line.player_id for team in (visitor, home) for line in team.players]
    duplicates = sorted(player for player, count in Counter(listed).items() if count > 1)
    checks.append(
        GamePilotCheck("players_listed_once", CHECK_PASSED)
        if not duplicates
        else _failed("players_listed_once", ", ".join(duplicates))
    )

    checks.append(_plus_minus_check(visitor, home))
    return checks


def _per_team(
    code: str,
    teams: tuple[BoxScoreTeam, BoxScoreTeam],
    problem: Callable[[BoxScoreTeam], str | None],
) -> GamePilotCheck:
    problems = [f"{team.code}: {detail}" for team in teams if (detail := problem(team))]
    return (
        GamePilotCheck(code, CHECK_PASSED) if not problems else _failed(code, "; ".join(problems))
    )


def _totals_problem(team: BoxScoreTeam) -> str | None:
    mismatches = []
    for stat in COUNTING_STATS:
        total = team.totals.get(stat)
        summed = _played_sum(team, stat)
        if total is None:
            mismatches.append(f"{stat} has no team total")
        elif summed is None:
            blank = sum(line.stats.get(stat) is None for line in team.played_lines)
            mismatches.append(f"{stat} blank on {blank} of {len(team.played_lines)} played lines")
        elif stat in TEAM_LEVEL_STATS and summed <= total:
            continue
        elif summed != total:
            mismatches.append(f"{stat} {summed} vs {total}")
    return "; ".join(mismatches) or None


def _played_sum(team: BoxScoreTeam, stat: str) -> int | None:
    """The stat summed over the played lines, or None when any of them is blank."""

    summed = 0
    for line in team.played_lines:
        value = line.stats.get(stat)
        if value is None:
            return None
        summed += value
    return summed


def _team_only_amount(team: BoxScoreTeam, stat: str) -> int | None:
    """What the team total holds beyond its player lines; None when that is unknowable."""

    total = team.totals.get(stat)
    summed = _played_sum(team, stat)
    if total is None or summed is None or summed > total:
        return None
    return total - summed


def _minutes_problem(team: BoxScoreTeam, overtime_periods: int) -> str | None:
    expected = (REGULATION_TEAM_MINUTES + OVERTIME_TEAM_MINUTES * overtime_periods) * 60
    missing = [line.player_id for line in team.played_lines if line.seconds_played is None]
    if missing:
        return f"no minutes for {', '.join(missing)}"
    if team.totals_seconds is None:
        return "no team total minutes"
    if team.totals_seconds != expected:
        return f"team total {team.totals_seconds}s, game length {expected}s"
    summed = sum(line.seconds_played or 0 for line in team.played_lines)
    tolerance = len(team.played_lines) / 2
    if abs(summed - expected) > tolerance:
        return f"players {summed}s, game length {expected}s, rounding allows {tolerance:g}s"
    return None


def _plus_minus_check(visitor: BoxScoreTeam, home: BoxScoreTeam) -> GamePilotCheck:
    code = "plus_minus_balances"
    # A line with 0:00 played carries a blank plus-minus; it contributes nothing.
    lines = [
        line for line in (*visitor.played_lines, *home.played_lines) if line.seconds_played != 0
    ]
    if all(line.plus_minus is None for line in lines):
        return GamePilotCheck(code, CHECK_NOT_CHECKED, "plus-minus is not published")
    if any(line.plus_minus is None for line in lines):
        return _failed(code, "plus-minus is missing for a player who played")
    if visitor.scorebox_points is None or home.scorebox_points is None:
        return GamePilotCheck(code, CHECK_NOT_CHECKED, "no final score")
    margin = visitor.scorebox_points - home.scorebox_points
    if margin != 0 and all(line.plus_minus == 0 for line in lines):
        return GamePilotCheck(
            code,
            CHECK_EXPECTED_GAP,
            "plus-minus is published as 0 for every player; treat it as missing",
        )
    sums = (
        sum(line.plus_minus or 0 for line in visitor.played_lines),
        sum(line.plus_minus or 0 for line in home.played_lines),
    )
    if sums != (5 * margin, -5 * margin):
        return _failed(code, f"sums {sums}, expected {(5 * margin, -5 * margin)}")
    return GamePilotCheck(code, CHECK_PASSED)


def _play_by_play_checks(
    pbp: ParsedPlayByPlay,
    visitor: BoxScoreTeam,
    home: BoxScoreTeam,
) -> list[GamePilotCheck]:
    checks: list[GamePilotCheck] = []
    final = (visitor.scorebox_points, home.scorebox_points)
    checks.append(
        GamePilotCheck("play_by_play_final_score", CHECK_PASSED)
        if pbp.final_score == final
        else _failed("play_by_play_final_score", f"events end {pbp.final_score}, box {final}")
    )

    line_periods = len(visitor.line_score)
    if not line_periods or len(home.line_score) != line_periods:
        # A missing or ragged line score is a data-quality failure, not a crash.
        detail = (
            f"no comparable line score ({visitor.code} {line_periods} periods, "
            f"{home.code} {len(home.line_score)})"
        )
        checks.append(_failed("play_by_play_periods", detail))
        checks.append(_failed("play_by_play_period_points", detail))
    else:
        checks.append(
            GamePilotCheck("play_by_play_periods", CHECK_PASSED)
            if pbp.periods == line_periods
            else _failed("play_by_play_periods", f"{pbp.periods} vs line score {line_periods}")
        )
        by_period = pbp.points_by_period()
        mismatched = [
            f"period {period}: events {by_period.get(period, (0, 0))}, line score {pair}"
            for period, pair in enumerate(zip(visitor.line_score, home.line_score, strict=True), 1)
            if by_period.get(period, (0, 0)) != pair
        ]
        checks.append(
            GamePilotCheck("play_by_play_period_points", CHECK_PASSED)
            if not mismatched
            else _failed("play_by_play_period_points", "; ".join(mismatched))
        )

    listed = {line.player_id for team in (visitor, home) for line in team.players} | {
        player for team in (visitor, home) for player in team.inactive_player_ids
    }
    unknown = sorted({pid for event in pbp.events for pid in event.player_ids} - listed)
    checks.append(
        GamePilotCheck("play_by_play_players_listed", CHECK_PASSED)
        if not unknown
        else _failed("play_by_play_players_listed", ", ".join(unknown))
    )

    checks.append(_player_points_check(pbp, visitor, home))
    return checks


def _player_points_check(
    pbp: ParsedPlayByPlay,
    visitor: BoxScoreTeam,
    home: BoxScoreTeam,
) -> GamePilotCheck:
    """Credit each scoring event to its first linked player and compare with the box."""

    code = "play_by_play_player_points"
    credited: Counter[str] = Counter()
    uncredited = 0
    for event in pbp.events:
        if event.points == 0 or event.side not in (SIDE_VISITOR, SIDE_HOME):
            continue
        if not event.player_ids:
            uncredited += event.points
            continue
        credited[event.player_ids[0]] += event.points

    boxed: dict[str, int] = {}
    blank: list[str] = []
    for team in (visitor, home):
        for line in team.played_lines:
            points = line.stats.get("pts")
            if points is None:
                blank.append(line.player_id)
            elif points:
                boxed[line.player_id] = points
    mismatches = sorted(
        f"{player} {credited.get(player, 0)} vs {boxed.get(player, 0)}"
        for player in (set(credited) | set(boxed)) - set(blank)
        if credited.get(player, 0) != boxed.get(player, 0)
    )
    if blank:
        mismatches.append(f"no points on the box score for {', '.join(sorted(blank))}")
    if uncredited:
        mismatches.append(f"{uncredited} points credited to no player")
    return (
        GamePilotCheck(code, CHECK_PASSED)
        if not mismatches
        else _failed(code, "; ".join(mismatches))
    )


def _play_by_play_profile(
    pbp: ParsedPlayByPlay,
    visitor: BoxScoreTeam,
    home: BoxScoreTeam,
) -> PlayByPlayProfile:
    """Count what a lineup reconstruction would meet, carrying lineups across periods."""

    on_floor = {
        SIDE_VISITOR: {line.player_id for line in visitor.players if line.starter},
        SIDE_HOME: {line.player_id for line in home.players if line.starter},
    }
    substitutions = 0
    groups: Counter[tuple[int, str, str]] = Counter()
    conflicts = 0
    for event in pbp.events:
        if event.side not in on_floor or SUBSTITUTION_MARKER not in event.description:
            continue
        substitutions += 1
        groups[(event.period, event.clock, event.side)] += 1
        if len(event.player_ids) != 2:
            conflicts += 1
            continue
        incoming, outgoing = event.player_ids
        lineup = on_floor[event.side]
        if outgoing not in lineup or incoming in lineup:
            conflicts += 1
        lineup.discard(outgoing)
        lineup.add(incoming)

    return PlayByPlayProfile(
        events=len(pbp.events),
        substitutions=substitutions,
        same_clock_substitution_groups=sum(1 for count in groups.values() if count > 1),
        review_events=sum(REVIEW_MARKER in event.description for event in pbp.events),
        lineup_carryover_conflicts=conflicts,
    )


def _team_identity_check(
    codes: tuple[str, str],
    season_end_year: int,
    known_team_seasons: frozenset[tuple[str, int]],
    beyond_archive: bool,
) -> tuple[GamePilotCheck, list[str]]:
    unresolved = [code for code in codes if (code, season_end_year) not in known_team_seasons]
    if not unresolved:
        return GamePilotCheck("team_seasons_resolve", CHECK_PASSED), []
    detail = f"{', '.join(unresolved)} {season_end_year} not in core.team_seasons"
    status = CHECK_EXPECTED_GAP if beyond_archive else CHECK_FAILED
    return GamePilotCheck("team_seasons_resolve", status, detail), unresolved


def _player_identity_check(
    teams: tuple[BoxScoreTeam, BoxScoreTeam],
    known_player_ids: frozenset[str],
    beyond_archive: bool,
) -> tuple[GamePilotCheck, list[str]]:
    lined = {line.player_id for team in teams for line in team.players}
    inactive_only = {player for team in teams for player in team.inactive_player_ids} - lined
    unresolved_lines = sorted(player for player in lined if player not in known_player_ids)
    unresolved_inactive = sorted(
        player for player in inactive_only if player not in known_player_ids
    )
    unresolved = unresolved_lines + unresolved_inactive
    total = len(lined) + len(inactive_only)
    if not unresolved:
        return GamePilotCheck("players_resolve", CHECK_PASSED, f"{total} players"), []

    parts = []
    if unresolved_lines:
        parts.append(f"with a box score line: {', '.join(unresolved_lines)}")
    if unresolved_inactive:
        parts.append(f"inactive only: {', '.join(unresolved_inactive)}")
    detail = f"{len(unresolved)} of {total} not in core.players ({'; '.join(parts)})"
    status = CHECK_EXPECTED_GAP if beyond_archive or not unresolved_lines else CHECK_FAILED
    return GamePilotCheck("players_resolve", status, detail), unresolved


def _measurements_by_url(reports: Iterable[Mapping[str, object]]) -> dict[str, _Measurement]:
    measured: dict[str, _Measurement] = {}
    for report in reports:
        entries = report.get("entries")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, Mapping) or entry.get("status") != "fetched":
                continue
            url = entry.get("url")
            requests = entry.get("requests")
            elapsed = entry.get("elapsed_seconds")
            if isinstance(url, str):
                measured[url] = _Measurement(
                    requests=requests if isinstance(requests, int) else None,
                    elapsed_seconds=float(elapsed) if isinstance(elapsed, int | float) else None,
                )
    return measured


def _failed(code: str, detail: str) -> GamePilotCheck:
    return GamePilotCheck(code, CHECK_FAILED, detail)


__all__ = [
    "CHECK_EXPECTED_GAP",
    "CHECK_FAILED",
    "CHECK_NOT_CHECKED",
    "CHECK_PASSED",
    "GamePilotCheck",
    "GamePilotGameResult",
    "GamePilotSchedulePage",
    "GamePilotValidationReport",
    "PlayByPlayProfile",
    "build_game_pilot_validation_report",
    "known_player_ids_from_cache",
]
