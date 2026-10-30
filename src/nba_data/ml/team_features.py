"""Leakage-proof pre-game team features, definition `team-pregame-v1`.

Results-based features (Elo, efficiencies, pace, margin, four factors) see only
history games dated at least `RESULTS_CUTOFF_DAYS` before the target, or on or
before an earlier explicit cutoff. Schedule features (rest, back-to-back, games
in the last seven days) read the schedule up to the target date, never results.

Windows reset each season; Elo is the only cross-season memory. A rate is
accumulated numerators over accumulated denominators, never a mean of per-game
rates. A window with no usable game gives `None`, never `0`.

Any change to a formula, window, or constant here bumps
`FEATURE_DEFINITION_VERSION`.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from nba_data.ml.elo import EloRatings
from nba_data.ml.team_games import (
    GAME_TYPE_REGULAR_SEASON,
    HISTORY_GAME_TYPES,
    STATUS_FINAL,
    TeamBox,
    TeamGameRecord,
)

FEATURE_DEFINITION_VERSION = "team-pregame-v1"

RESULTS_CUTOFF_DAYS = 2
REST_DAYS_CAP = 7
DENSITY_DAYS = 7
STATUS_POSTPONED = "postponed"

# `None` is season-to-date.
WINDOWS: tuple[tuple[str, int | None], ...] = (
    ("l5", 5),
    ("l10", 10),
    ("l20", 20),
    ("season", None),
)

FeatureValue = float | int | bool | None
# A game's contribution to one rate: (numerator, denominator), or `None` when a
# counter it needs is blank.
Contribution = tuple[float, float] | None


def _possessions(own: TeamBox, opp: TeamBox) -> float | None:
    """`fga + 0.44·fta − orb + tov`, averaged over both teams of the game."""

    estimates = []
    for box in (own, opp):
        if box.fga is None or box.fta is None or box.orb is None or box.tov is None:
            return None
        estimates.append(box.fga + 0.44 * box.fta - box.orb + box.tov)
    return (estimates[0] + estimates[1]) / 2


def _off_rtg(own: TeamBox, opp: TeamBox) -> Contribution:
    poss = _possessions(own, opp)
    if poss is None or own.pts is None:
        return None
    return 100.0 * own.pts, poss


def _def_rtg(own: TeamBox, opp: TeamBox) -> Contribution:
    poss = _possessions(own, opp)
    if poss is None or opp.pts is None:
        return None
    return 100.0 * opp.pts, poss


def _net_rtg(own: TeamBox, opp: TeamBox) -> Contribution:
    poss = _possessions(own, opp)
    if poss is None or own.pts is None or opp.pts is None:
        return None
    return 100.0 * (own.pts - opp.pts), poss


def _pace(own: TeamBox, opp: TeamBox) -> Contribution:
    """Possessions per 48 minutes; a game lasts `seconds_played / 5 / 60` minutes."""

    poss = _possessions(own, opp)
    if poss is None or own.seconds_played is None:
        return None
    return 48.0 * poss, own.seconds_played / 5 / 60


def _margin(own: TeamBox, opp: TeamBox) -> Contribution:
    if own.pts is None or opp.pts is None:
        return None
    return float(own.pts - opp.pts), 1.0


def _efg_pct(own: TeamBox, opp: TeamBox) -> Contribution:
    if own.fg is None or own.fg3 is None or own.fga is None:
        return None
    return own.fg + 0.5 * own.fg3, float(own.fga)


def _tov_pct(own: TeamBox, opp: TeamBox) -> Contribution:
    if own.tov is None or own.fga is None or own.fta is None:
        return None
    return float(own.tov), own.fga + 0.44 * own.fta + own.tov


def _orb_pct(own: TeamBox, opp: TeamBox) -> Contribution:
    if own.orb is None or opp.drb is None:
        return None
    return float(own.orb), float(own.orb + opp.drb)


def _ft_rate(own: TeamBox, opp: TeamBox) -> Contribution:
    if own.ft is None or own.fga is None:
        return None
    return float(own.ft), float(own.fga)


RESULT_METRICS: dict[str, Callable[[TeamBox, TeamBox], Contribution]] = {
    "off_rtg": _off_rtg,
    "def_rtg": _def_rtg,
    "net_rtg": _net_rtg,
    "pace": _pace,
    "margin": _margin,
    "efg_pct": _efg_pct,
    "tov_pct": _tov_pct,
    "orb_pct": _orb_pct,
    "ft_rate": _ft_rate,
}

FEATURE_NAMES: tuple[str, ...] = (
    "elo_home",
    "elo_away",
    "elo_diff",
    "is_neutral",
    "games_in_season_before_home",
    "games_in_season_before_away",
    "diff_rest_days",
    "diff_back_to_back",
    "diff_games_last_7_days",
    *(f"diff_{metric}_{window}" for metric in RESULT_METRICS for window, _ in WINDOWS),
)


@dataclass(frozen=True)
class TeamFeatureRow:
    game_id: str
    game_date: date
    season_year: int
    home_team: str
    away_team: str
    # Keyed by `FEATURE_NAMES`, in that order.
    values: dict[str, FeatureValue]


@dataclass(frozen=True)
class TeamFeatureBuild:
    version: str
    # In `(game_date, game_id)` order.
    rows: list[TeamFeatureRow]
    # History games each result feature (and Elo) could not use, by feature,
    # over all supplied history: not per target, and not limited to any cutoff.
    skipped_games: dict[str, int]
    # Games whose undetermined `neutral_site` was treated as a home game, by
    # Elo or as a target's `is_neutral`.
    null_neutral_as_home: int


@dataclass(frozen=True)
class _TeamGame:
    game_date: date
    contributions: dict[str, Contribution]


def build_team_features(
    games: Iterable[TeamGameRecord],
    *,
    target_ids: Collection[str],
    cutoff: date | None = None,
) -> TeamFeatureBuild:
    """One row of pre-game features per target game.

    `games` is the schedule and the history together. History is every `final`
    game of type `regular_season` or `cup_final`; the schedule is every game not
    postponed. Every target must be a `regular_season` game in `games` that is
    not postponed.
    """

    by_id = _index_games(games)
    targets = _resolve_targets(by_id, target_ids)
    ordered = sorted(by_id.values(), key=lambda game: (game.game_date, game.game_id))
    history = [
        game
        for game in ordered
        if game.status == STATUS_FINAL and game.game_type in HISTORY_GAME_TYPES
    ]

    skipped: dict[str, int] = dict.fromkeys(("elo", *RESULT_METRICS), 0)
    team_history: dict[tuple[str, int], list[_TeamGame]] = defaultdict(list)
    for game in history:
        if game.home.pts is None or game.away.pts is None:
            skipped["elo"] += 1
        per_side = (
            (game.home, _contributions(game.home, game.away)),
            (game.away, _contributions(game.away, game.home)),
        )
        for metric in RESULT_METRICS:
            if any(contributions[metric] is None for _, contributions in per_side):
                skipped[metric] += 1
        for box, contributions in per_side:
            team_history[(box.team_code, game.season_year)].append(
                _TeamGame(game.game_date, contributions)
            )
    history_dates = {
        key: [team_game.game_date for team_game in team_games]
        for key, team_games in team_history.items()
    }

    schedule: dict[tuple[str, int], list[date]] = defaultdict(list)
    for game in ordered:
        if game.status != STATUS_POSTPONED:
            for box in (game.home, game.away):
                schedule[(box.team_code, game.season_year)].append(game.game_date)

    effective_cutoffs = {target.game_id: _results_cutoff(target, cutoff) for target in targets}
    elo_by_target, null_neutral = _pregame_elo(history, targets, effective_cutoffs)
    null_neutral.update(target.game_id for target in targets if target.neutral_site is None)

    rows = []
    for target in targets:
        results_cutoff = effective_cutoffs[target.game_id]
        elo_home, elo_away = elo_by_target[target.game_id]
        sides = []
        for box in (target.home, target.away):
            key = (box.team_code, target.season_year)
            known = bisect_right(history_dates.get(key, []), results_cutoff)
            sides.append(
                (
                    _window_values(team_history.get(key, [])[:known]),
                    _schedule_values(schedule.get(key, []), target.game_date),
                    known,
                )
            )
        (home_windows, home_schedule, home_known), (away_windows, away_schedule, away_known) = sides

        values: dict[str, FeatureValue] = {
            "elo_home": elo_home,
            "elo_away": elo_away,
            "elo_diff": elo_home - elo_away,
            "is_neutral": target.neutral_site is True,
            "games_in_season_before_home": home_known,
            "games_in_season_before_away": away_known,
        }
        for name in ("rest_days", "back_to_back", "games_last_7_days"):
            values[f"diff_{name}"] = _difference(home_schedule[name], away_schedule[name])
        for name, home_value in home_windows.items():
            values[f"diff_{name}"] = _difference(home_value, away_windows[name])
        rows.append(
            TeamFeatureRow(
                game_id=target.game_id,
                game_date=target.game_date,
                season_year=target.season_year,
                home_team=target.home.team_code,
                away_team=target.away.team_code,
                values={name: values[name] for name in FEATURE_NAMES},
            )
        )

    return TeamFeatureBuild(
        version=FEATURE_DEFINITION_VERSION,
        rows=rows,
        skipped_games=skipped,
        null_neutral_as_home=len(null_neutral),
    )


def _index_games(games: Iterable[TeamGameRecord]) -> dict[str, TeamGameRecord]:
    by_id: dict[str, TeamGameRecord] = {}
    for game in games:
        if game.game_id in by_id:
            raise ValueError(f"{game.game_id}: game appears twice")
        by_id[game.game_id] = game
    return by_id


def _resolve_targets(
    by_id: dict[str, TeamGameRecord], target_ids: Collection[str]
) -> list[TeamGameRecord]:
    if isinstance(target_ids, str):
        raise TypeError("target_ids must be a collection of game ids, not one string")
    targets = []
    for game_id in set(target_ids):
        target = by_id.get(game_id)
        if target is None:
            raise ValueError(f"{game_id}: target is not among the games")
        if target.status == STATUS_POSTPONED:
            raise ValueError(f"{game_id}: a postponed game has no date to predict for")
        if target.game_type is None:
            # A scheduled game is stored unclassified; F8-010 must classify it first.
            raise ValueError(f"{game_id}: target has no competition type yet")
        if target.game_type != GAME_TYPE_REGULAR_SEASON:
            raise ValueError(f"{game_id}: only regular-season games are targets")
        targets.append(target)
    return sorted(targets, key=lambda game: (game.game_date, game.game_id))


def _results_cutoff(target: TeamGameRecord, cutoff: date | None) -> date:
    latest = target.game_date - timedelta(days=RESULTS_CUTOFF_DAYS)
    return latest if cutoff is None else min(latest, cutoff)


def _contributions(own: TeamBox, opp: TeamBox) -> dict[str, Contribution]:
    return {metric: compute(own, opp) for metric, compute in RESULT_METRICS.items()}


def _pregame_elo(
    history: list[TeamGameRecord],
    targets: list[TeamGameRecord],
    effective_cutoffs: dict[str, date],
) -> tuple[dict[str, tuple[float, float]], set[str]]:
    """Each target's two ratings after every scored history game up to its cutoff.

    One sweep: targets in cutoff order, history in `(game_date, game_id)` order.
    """

    ratings = EloRatings()
    scored = [game for game in history if game.home.pts is not None and game.away.pts is not None]
    null_neutral: set[str] = set()
    elo_by_target: dict[str, tuple[float, float]] = {}
    position = 0
    for target in sorted(targets, key=lambda game: effective_cutoffs[game.game_id]):
        results_cutoff = effective_cutoffs[target.game_id]
        while position < len(scored) and scored[position].game_date <= results_cutoff:
            game = scored[position]
            ratings.update(game)
            if game.neutral_site is None:
                null_neutral.add(game.game_id)
            position += 1
        elo_by_target[target.game_id] = (
            ratings.pregame(target.home.team_code, target.season_year),
            ratings.pregame(target.away.team_code, target.season_year),
        )
    return elo_by_target, null_neutral


def _window_values(team_games: list[_TeamGame]) -> dict[str, float | None]:
    values: dict[str, float | None] = {}
    for metric in RESULT_METRICS:
        for window, size in WINDOWS:
            in_window = team_games if size is None else team_games[-size:]
            values[f"{metric}_{window}"] = _rate(
                team_game.contributions[metric] for team_game in in_window
            )
    return values


def _rate(contributions: Iterable[Contribution]) -> float | None:
    numerator = denominator = 0.0
    used = 0
    for contribution in contributions:
        if contribution is None:
            continue
        numerator += contribution[0]
        denominator += contribution[1]
        used += 1
    if used == 0 or denominator == 0:
        return None
    return numerator / denominator


def _schedule_values(dates: list[date], game_date: date) -> dict[str, int | None]:
    earlier = dates[: bisect_right(dates, game_date - timedelta(days=1))]
    if not earlier:
        return {"rest_days": None, "back_to_back": 0, "games_last_7_days": 0}
    window_start = game_date - timedelta(days=DENSITY_DAYS)
    return {
        "rest_days": min((game_date - earlier[-1]).days - 1, REST_DAYS_CAP),
        "back_to_back": int(earlier[-1] == game_date - timedelta(days=1)),
        "games_last_7_days": sum(1 for played in earlier if played >= window_start),
    }


def _difference(home: FeatureValue, away: FeatureValue) -> FeatureValue:
    if home is None or away is None:
        return None
    return home - away
