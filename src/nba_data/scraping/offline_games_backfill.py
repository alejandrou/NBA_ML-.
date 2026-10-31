"""Load cached schedules and box scores into the game tables, offline (F8-005).

For each season, the games are the ones F8-004 selects from the cached month
pages (`select_season_games`): the regular season plus the NBA Cup final. Each
selected game whose box score is cached is gated and loaded by `load_game` in
its own transaction, committed before the next; a quarantined or failed game
writes nothing and the others still load. A game whose box score is not cached
is coverage (`missing_box_score`), not a row. When this run loaded every
selected game, or quarantined it, a second pass derives `neutral_site` from the
venues of the whole season; a missing box score or a failed load defers it, even
when an earlier run stored that game.

Only the cache is read. No HTTP client is constructed here and nothing is
fetched; a page that is not cached stays missing.
"""

from __future__ import annotations

import zlib
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.game_pilot_manifest import box_score_url
from nba_data.scraping.game_season_planning import (
    EXPECTED_SELECTED_GAMES,
    GameSeasonPlanningError,
    select_season_games,
)
from nba_data.scraping.loaders.games import GameLineage, derive_neutral_sites, load_game
from nba_data.scraping.parsers.box_score import (
    GAME_TYPE_PLAY_IN,
    GAME_TYPE_PLAYOFFS,
    parse_box_score_page,
)
from nba_data.validation.parser_contracts import current_parser_version

DEFAULT_GAMES_PARSER_VERSION = current_parser_version("box_score")
SCHEDULE_PARSER_VERSION = current_parser_version("league_schedule")
# The selection keeps the regular season and the Cup final; a heading that
# says otherwise is loaded with its own type and listed for review.
UNEXPECTED_GAME_TYPES = frozenset({GAME_TYPE_PLAY_IN, GAME_TYPE_PLAYOFFS})


@dataclass
class SeasonGamesReport:
    season_end_year: int
    parser_version: str
    selection_error: str | None = None
    selection_rule: str | None = None
    expected: int = 0
    loaded: int = 0
    unchanged: int = 0
    missing_box_score: list[str] = field(default_factory=list)
    quarantined: dict[str, list[str]] = field(default_factory=dict)
    quarantine_details: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)
    warnings: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    players_created: list[str] = field(default_factory=list)
    neutral_games: list[dict[str, str]] = field(default_factory=list)
    neutral_site_updates: int = 0
    game_types: Counter[str] = field(default_factory=Counter)
    unexpected_game_types: dict[str, list[str]] = field(default_factory=dict)

    @property
    def quarantined_games(self) -> int:
        return len(self.quarantine_details)

    @property
    def problems(self) -> list[str]:
        """Why this season fails, ignoring box scores not yet cached."""

        problems: list[str] = []
        if self.selection_error is not None:
            problems.append(f"no games selected: {self.selection_error}")
        elif self.expected == 0:
            problems.append("no games selected")
        if self.quarantine_details:
            problems.append(f"{self.quarantined_games} game(s) quarantined")
        if self.failed:
            problems.append(f"{len(self.failed)} game(s) failed to load")
        return problems

    def to_dict(self) -> dict[str, object]:
        return {
            "season_end_year": self.season_end_year,
            "parser_version": self.parser_version,
            "schedule_parser_version": SCHEDULE_PARSER_VERSION,
            "selection_rule": self.selection_rule,
            "selection_error": self.selection_error,
            "expected": self.expected,
            "loaded": self.loaded,
            "unchanged": self.unchanged,
            "missing_box_score": list(self.missing_box_score),
            "quarantined_games": self.quarantined_games,
            "quarantined": {reason: list(ids) for reason, ids in sorted(self.quarantined.items())},
            "quarantine_details": dict(sorted(self.quarantine_details.items())),
            "failed": dict(sorted(self.failed.items())),
            "warnings": dict(sorted(self.warnings.items())),
            "players_created": sorted(self.players_created),
            "neutral_games": list(self.neutral_games),
            "neutral_site_updates": self.neutral_site_updates,
            "game_types": dict(sorted(self.game_types.items())),
            "unexpected_game_types": {
                game_type: list(ids)
                for game_type, ids in sorted(self.unexpected_game_types.items())
            },
            "problems": self.problems,
        }


@dataclass(frozen=True)
class OfflineGamesBackfillReport:
    seasons: tuple[SeasonGamesReport, ...]

    def failed(self, *, require_complete: bool = False) -> bool:
        if not self.seasons:
            return True
        return any(
            season.problems or (require_complete and season.missing_box_score)
            for season in self.seasons
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "seasons": [season.to_dict() for season in self.seasons],
            "expected": sum(season.expected for season in self.seasons),
            "loaded": sum(season.loaded for season in self.seasons),
            "unchanged": sum(season.unchanged for season in self.seasons),
            "missing_box_score": sum(len(season.missing_box_score) for season in self.seasons),
            "quarantined_games": sum(season.quarantined_games for season in self.seasons),
            "failed_games": sum(len(season.failed) for season in self.seasons),
        }


def run_offline_games_backfill(
    session: Session,
    *,
    cache: HtmlCache,
    season_end_years: Iterable[int],
    expected_counts: Mapping[int, int] = EXPECTED_SELECTED_GAMES,
    parser_version: str = DEFAULT_GAMES_PARSER_VERSION,
) -> OfflineGamesBackfillReport:
    """Load each season's cached games, committing one game at a time."""

    seasons = list(dict.fromkeys(season_end_years))
    if not parser_version.strip():
        msg = "parser_version is required"
        raise ValueError(msg)
    return OfflineGamesBackfillReport(
        seasons=tuple(
            _backfill_season(
                session,
                cache=cache,
                season_end_year=season,
                expected_counts=expected_counts,
                parser_version=parser_version,
            )
            for season in seasons
        )
    )


def _backfill_season(
    session: Session,
    *,
    cache: HtmlCache,
    season_end_year: int,
    expected_counts: Mapping[int, int],
    parser_version: str,
) -> SeasonGamesReport:
    report = SeasonGamesReport(season_end_year=season_end_year, parser_version=parser_version)
    try:
        selection = select_season_games(
            season_end_year, cache=cache, expected_counts=expected_counts
        )
    except (GameSeasonPlanningError, OSError, EOFError, UnicodeError, zlib.error) as exc:
        report.selection_error = str(exc)
        return report

    report.selection_rule = selection.rule
    report.expected = len(selection.games)
    for game in selection.games:
        assert game.game_id is not None  # the selection keeps played rows only
        url = box_score_url(game.game_id)
        lineage = GameLineage(
            source_url=url,
            cache_path=str(cache.path_for_url(url)),
            parser_version=parser_version,
        )
        try:
            html = cache.get(url)
            if html is None:
                report.missing_box_score.append(game.game_id)
                continue
            result = load_game(
                session,
                game,
                parse_box_score_page(html),
                lineage,
                season_end_year=season_end_year,
            )
            if result.status == "quarantined":
                session.rollback()
            else:
                session.commit()
        except Exception as exc:  # one game's failure must not take the season with it
            session.rollback()
            report.failed[game.game_id] = f"{type(exc).__name__}: {exc}"
            continue

        if result.warnings:
            report.warnings[game.game_id] = [issue.to_dict() for issue in result.warnings]
        if result.status == "quarantined":
            report.quarantine_details[game.game_id] = [
                issue.to_dict() for issue in result.quarantine
            ]
            for reason in dict.fromkeys(issue.code for issue in result.quarantine):
                report.quarantined.setdefault(reason, []).append(game.game_id)
            continue

        if result.status == "loaded":
            report.loaded += 1
        else:
            report.unchanged += 1
        report.players_created.extend(result.players_created)
        if result.game_type is not None:
            report.game_types[result.game_type] += 1
            if result.game_type in UNEXPECTED_GAME_TYPES:
                report.unexpected_game_types.setdefault(result.game_type, []).append(game.game_id)

    try:
        neutral = derive_neutral_sites(
            session, season_end_year,
            expected_game_ids=frozenset(
                game.game_id for game in selection.games if game.game_id is not None
            ),
            quarantined_game_ids=frozenset(report.quarantine_details),
            unloaded_game_ids=frozenset(report.missing_box_score) | frozenset(report.failed),
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        report.failed["neutral_site"] = f"{type(exc).__name__}: {exc}"
        return report
    report.neutral_site_updates = neutral.updated
    report.neutral_games = [
        {"game_id": game_id, "venue": venue} for game_id, venue in neutral.neutral_games
    ]
    if neutral.warnings:
        report.warnings["neutral_site"] = [issue.to_dict() for issue in neutral.warnings]
    return report


__all__ = [
    "DEFAULT_GAMES_PARSER_VERSION",
    "SCHEDULE_PARSER_VERSION",
    "OfflineGamesBackfillReport",
    "SeasonGamesReport",
    "run_offline_games_backfill",
]
