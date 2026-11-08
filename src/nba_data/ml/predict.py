"""Write one model's forecasts for a window of games into `ml.predictions`.

The cutoff is `min(game_date - 2 days, latest complete date)`. A date is complete
when no game on or before it is still `scheduled`: a game left behind stops the
cutoff there, so a forecast never treats a missing result as a game not played.
Postponed games have no result to wait for.

Schedule pages do not mark a coming playoff, play-in, or Cup final game, and
`neutral_site` stays NULL while a season is in progress. Publication resolves the
venue from arena names, without writing to `core`, and withholds what it cannot
confirm: an unclassified game is forecast only on its home team's floor and
within the team's 82 games. A withheld game gets no row and is named in the report.

Rows are written once. A game no longer `scheduled` gets a row only if this model
has none for it, so a later run cannot bury an issued forecast. The caller owns
the transaction.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections import Counter, defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import astuple, dataclass, replace
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, aliased

from nba_data.db.models import Game, ModelVersion, Prediction, Season, Team, TeamSeason
from nba_data.ml.artifact import ArtifactIntegrityError, load_artifact
from nba_data.ml.models import WinProbabilityModel
from nba_data.ml.team_features import (
    FEATURE_DEFINITION_VERSION,
    RESULTS_CUTOFF_DAYS,
    STATUS_POSTPONED,
    TeamFeatureRow,
    build_team_features,
)
from nba_data.ml.team_games import (
    GAME_TYPE_REGULAR_SEASON,
    HISTORY_GAME_TYPES,
    STATUS_FINAL,
    TeamBox,
    TeamGameRecord,
    load_team_game_history,
)

STATUS_SCHEDULED = "scheduled"
PREDICTION_AVAILABLE = "available"
PREDICTION_UNAVAILABLE = "unavailable"
REASON_INSUFFICIENT_HISTORY = "insufficient_history"
REASON_GAME_NOT_SCHEDULED = "game_not_scheduled"
FAVORITE_HOME = "home"
FAVORITE_AWAY = "away"

WITHHELD_NOT_REGULAR_SEASON = "not_regular_season"
WITHHELD_UNKNOWN_VENUE = "unknown_venue"
WITHHELD_UNCONFIRMED_COMPETITION = "unconfirmed_competition"

# The shortest feature window: each team's last five games must all be complete.
MIN_PRIOR_GAMES = 5
REGULAR_SEASON_GAMES = 82
# Fewer home games than this cannot establish which arena is the team's own.
MIN_HOME_ARENA_GAMES = 3
_PROBABILITY_PLACES = Decimal("0.000001")
_ONE = Decimal(1)
_EVEN = Decimal("0.5")
_UNIQUE_KEY = "uq_ml_predictions_game_model_cutoff"


class PredictionError(ValueError):
    """The forecasts cannot be issued; nothing was written."""


@dataclass(frozen=True)
class WindowGame:
    id: int
    game_id: str
    game_date: date
    status: str
    game_type: str | None


@dataclass(frozen=True)
class Fixture:
    """What the venue and competition rules read about one game of the season."""

    game_id: str
    season_year: int
    game_date: date
    status: str
    game_type: str | None
    neutral_site: bool | None
    venue: str | None
    home_team: str
    away_team: str


@dataclass(frozen=True)
class PredictionReport:
    model: str
    start: date
    end: date
    latest_complete_date: date
    games: int
    written: int
    unchanged: int
    statuses: dict[str, int]
    # Finished or postponed games left with the rows already issued.
    kept_issued: int
    # These still hold an `available` row; the API must not serve it as live.
    postponed_with_forecast: list[str]
    withheld: dict[str, list[str]]
    # Forecasts refused because a recent game has blank statistics.
    blocked_by_blank_statistics: int
    # Results this season still counted as a home game: Elo cannot tell otherwise.
    history_venues_unresolved: int

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "from": self.start.isoformat(),
            "to": self.end.isoformat(),
            "latest_complete_date": self.latest_complete_date.isoformat(),
            "games": self.games,
            "written": self.written,
            "unchanged": self.unchanged,
            "statuses": self.statuses,
            "kept_issued": self.kept_issued,
            "postponed_with_forecast": self.postponed_with_forecast,
            "withheld": self.withheld,
            "blocked_by_blank_statistics": self.blocked_by_blank_statistics,
            "history_venues_unresolved": self.history_venues_unresolved,
        }


def latest_complete_date(schedule: Iterable[tuple[date, str]]) -> date | None:
    """The last date with a final game and no unfinished game on or before it."""

    entries = list(schedule)
    unfinished = [played for played, status in entries if status == STATUS_SCHEDULED]
    first_unfinished = min(unfinished, default=None)
    finished = (
        played
        for played, status in entries
        if status == STATUS_FINAL and (first_unfinished is None or played < first_unfinished)
    )
    return max(finished, default=None)


def cutoff_for(game_date: date, latest_complete: date) -> date:
    return min(game_date - timedelta(days=RESULTS_CUTOFF_DAYS), latest_complete)


def round_probabilities(home_probability: float) -> tuple[Decimal, Decimal, str | None]:
    """Home rounded half-even to six places, away its complement, and the favorite."""

    if not math.isfinite(home_probability) or not 0 <= home_probability <= 1:
        raise PredictionError(f"the model returned an invalid probability: {home_probability!r}")
    home = Decimal(home_probability).quantize(_PROBABILITY_PLACES, rounding=ROUND_HALF_EVEN)
    favorite = None
    if home != _EVEN:
        favorite = FAVORITE_HOME if home > _EVEN else FAVORITE_AWAY
    return home, _ONE - home, favorite


def resolve_neutral_sites(fixtures: Sequence[Fixture]) -> dict[str, bool | None]:
    """Each game's venue: a stored flag wins, otherwise its arena against the team's own.

    A team's arena is the one most of its home games that season list, final or
    still scheduled. No arena, a tie, or too few games leaves it undetermined.
    """

    counts: defaultdict[tuple[str, int], Counter[str]] = defaultdict(Counter)
    for fixture in fixtures:
        arena = _arena(fixture.venue)
        if arena is not None:
            counts[(fixture.home_team, fixture.season_year)][arena] += 1

    resolved: dict[str, bool | None] = {}
    for fixture in fixtures:
        if fixture.neutral_site is not None:
            resolved[fixture.game_id] = fixture.neutral_site
            continue
        arena = _arena(fixture.venue)
        own = _own_arena(counts.get((fixture.home_team, fixture.season_year)))
        resolved[fixture.game_id] = None if arena is None or own is None else arena != own
    return resolved


def games_past_the_regular_season(fixtures: Sequence[Fixture]) -> set[str]:
    """Games beyond either team's 82nd. A known Cup final does not count toward them."""

    by_team: defaultdict[tuple[str, int], list[Fixture]] = defaultdict(list)
    for fixture in fixtures:
        if fixture.status != STATUS_POSTPONED and fixture.game_type in (
            None,
            GAME_TYPE_REGULAR_SEASON,
        ):
            by_team[(fixture.home_team, fixture.season_year)].append(fixture)
            by_team[(fixture.away_team, fixture.season_year)].append(fixture)
    return {
        fixture.game_id
        for team_games in by_team.values()
        for fixture in sorted(team_games, key=lambda game: (game.game_date, game.game_id))[
            REGULAR_SEASON_GAMES:
        ]
    }


def withheld_games(
    window: Sequence[WindowGame],
    neutral_sites: Mapping[str, bool | None],
    past_regular_season: Collection[str],
) -> dict[str, list[str]]:
    """The scheduled games no forecast may be issued for, by reason."""

    withheld: defaultdict[str, list[str]] = defaultdict(list)
    for game in window:
        if game.status != STATUS_SCHEDULED:
            continue
        neutral = neutral_sites.get(game.game_id)
        if game.game_type not in (None, GAME_TYPE_REGULAR_SEASON):
            withheld[WITHHELD_NOT_REGULAR_SEASON].append(game.game_id)
        elif neutral is None:
            withheld[WITHHELD_UNKNOWN_VENUE].append(game.game_id)
        elif game.game_type is None and (neutral or game.game_id in past_regular_season):
            withheld[WITHHELD_UNCONFIRMED_COMPETITION].append(game.game_id)
    return {reason: sorted(ids) for reason, ids in sorted(withheld.items())}


def publish_predictions(
    session: Session,
    *,
    start: date,
    end: date,
    artifact_dir: Path,
    model_name: str | None = None,
) -> PredictionReport:
    """Forecast every game dated in `[start, end]` with the active or the named model."""

    if start > end:
        raise PredictionError(f"--from {start} is after --to {end}")
    version = _model_version(session, model_name)
    model = _load_model(version, artifact_dir)

    latest_complete = latest_complete_date(_schedule(session))
    if latest_complete is None:
        raise PredictionError("no date is complete yet, so no cutoff exists")
    window = _window_games(session, start, end)
    if not window:
        raise PredictionError(f"no game is dated between {start} and {end}")

    fixtures = _season_fixtures(session, start, end)
    neutral_sites = resolve_neutral_sites(fixtures)
    withheld = withheld_games(window, neutral_sites, games_past_the_regular_season(fixtures))
    games = [
        replace(game, neutral_site=neutral_sites.get(game.game_id, game.neutral_site))
        for game in load_team_game_history(session) + _load_unfinished_games(session)
    ]
    issued = _games_with_a_row(session, version.id, start, end)
    forecast = _games_with_a_row(session, version.id, start, end, PREDICTION_AVAILABLE)
    rows = build_prediction_rows(
        model,
        games,
        window,
        latest_complete,
        version.id,
        {game_id for ids in withheld.values() for game_id in ids},
        issued,
    )
    seasons = {fixture.season_year for fixture in fixtures}

    written = _insert(session, rows)
    return PredictionReport(
        model=version.name,
        start=start,
        end=end,
        latest_complete_date=latest_complete,
        games=len(window),
        written=written,
        unchanged=len(rows) - written,
        statuses=dict(
            sorted(Counter(row["unavailable_reason"] or row["status"] for row in rows).items())
        ),
        kept_issued=sum(
            1 for game in window if game.status != STATUS_SCHEDULED and game.game_id in issued
        ),
        postponed_with_forecast=sorted(
            game.game_id
            for game in window
            if game.status == STATUS_POSTPONED and game.game_id in forecast
        ),
        withheld=withheld,
        blocked_by_blank_statistics=sum(1 for row in rows if _blocked_by_blanks(row)),
        history_venues_unresolved=sum(
            1
            for game in games
            if game.status == STATUS_FINAL
            and game.season_year in seasons
            and game.neutral_site is None
        ),
    )


def build_prediction_rows(
    model: WinProbabilityModel,
    games: Sequence[TeamGameRecord],
    window: Sequence[WindowGame],
    latest_complete: date,
    model_version_id: int,
    skipped: Collection[str] = frozenset(),
    already_issued: Collection[str] = frozenset(),
) -> list[dict[str, Any]]:
    """One row per window game, from results dated on or before each game's cutoff.

    `already_issued` names the games this model has a row for: one no longer
    scheduled keeps those rows and gets no other.
    """

    targets = {
        game.game_id: game
        for game in window
        if game.status == STATUS_SCHEDULED and game.game_id not in skipped
    }
    features = _feature_rows(games, targets, latest_complete)
    history = _team_history(games)
    inputs = {
        game_id: {**row.values, **_history_diagnostics(row, history, latest_complete)}
        for game_id, row in features.items()
    }
    ready = [row for game_id, row in features.items() if _has_complete_history(inputs[game_id])]
    if ready:
        # Only Elo reads these, and it would otherwise see results past the cutoff.
        seasons = {row.season_year for row in ready}
        model.observe(
            game
            for game in games
            if game.status == STATUS_FINAL
            and game.season_year in seasons
            and game.game_date <= latest_complete
        )
        probabilities = dict(
            zip(
                (row.game_id for row in ready),
                (round_probabilities(p) for p in model.predict_proba(ready)),
                strict=True,
            )
        )
    else:
        probabilities = {}

    rows = []
    for game in window:
        if game.game_id in skipped or (
            game.game_id not in targets and game.game_id in already_issued
        ):
            continue
        common = {
            "game_id": game.id,
            "model_version_id": model_version_id,
            "cutoff_date": cutoff_for(game.game_date, latest_complete),
        }
        if game.game_id not in targets:
            rows.append(_unavailable(common, REASON_GAME_NOT_SCHEDULED, {}))
        elif game.game_id not in probabilities:
            rows.append(_unavailable(common, REASON_INSUFFICIENT_HISTORY, inputs[game.game_id]))
        else:
            home, away, favorite = probabilities[game.game_id]
            rows.append(
                {
                    **common,
                    "status": PREDICTION_AVAILABLE,
                    "unavailable_reason": None,
                    "home_win_probability": home,
                    "away_win_probability": away,
                    "favorite": favorite,
                    "inputs": inputs[game.game_id],
                }
            )
    return rows


def _feature_rows(
    games: Sequence[TeamGameRecord],
    targets: Mapping[str, WindowGame],
    latest_complete: date,
) -> dict[str, TeamFeatureRow]:
    if not targets:
        return {}
    classified = [
        replace(game, game_type=GAME_TYPE_REGULAR_SEASON)
        if game.game_id in targets and game.game_type is None
        else game
        for game in games
    ]
    build = build_team_features(classified, target_ids=set(targets), cutoff=latest_complete)
    return {row.game_id: row for row in build.rows}


def _team_history(
    games: Sequence[TeamGameRecord],
) -> dict[tuple[str, int], list[tuple[date, bool]]]:
    """Per team-season, in date order: each history game and whether its box is complete."""

    history: defaultdict[tuple[str, int], list[tuple[date, bool]]] = defaultdict(list)
    for game in games:
        if game.status == STATUS_FINAL and game.game_type in HISTORY_GAME_TYPES:
            complete = _box_complete(game.home) and _box_complete(game.away)
            for box in (game.home, game.away):
                history[(box.team_code, game.season_year)].append((game.game_date, complete))
    for team_games in history.values():
        team_games.sort(key=lambda entry: entry[0])
    return history


def _box_complete(box: TeamBox) -> bool:
    return all(value is not None for value in astuple(box))


def _history_diagnostics(
    row: TeamFeatureRow,
    history: Mapping[tuple[str, int], Sequence[tuple[date, bool]]],
    latest_complete: date,
) -> dict[str, int]:
    """How many of each team's last five known games have every statistic."""

    cutoff = cutoff_for(row.game_date, latest_complete)
    diagnostics = {}
    for side, team in (("home", row.home_team), ("away", row.away_team)):
        team_games = history.get((team, row.season_year), [])
        known = bisect_right([played for played, _ in team_games], cutoff)
        recent = team_games[max(known - MIN_PRIOR_GAMES, 0) : known]
        diagnostics[f"complete_recent_games_{side}"] = sum(1 for _, complete in recent if complete)
    return diagnostics


def _has_complete_history(inputs: Mapping[str, Any]) -> bool:
    return (
        min(inputs["complete_recent_games_home"], inputs["complete_recent_games_away"])
        >= MIN_PRIOR_GAMES
    )


def _blocked_by_blanks(row: Mapping[str, Any]) -> bool:
    inputs = row["inputs"]
    return (
        row["unavailable_reason"] == REASON_INSUFFICIENT_HISTORY
        and min(inputs["games_in_season_before_home"], inputs["games_in_season_before_away"])
        >= MIN_PRIOR_GAMES
    )


def _arena(venue: str | None) -> str | None:
    """The arena of a schedule's 'Arena' or a box score's 'Arena, City, State'."""

    arena = (venue or "").split(",", maxsplit=1)[0].strip().casefold()
    return arena or None


def _own_arena(arenas: Counter[str] | None) -> str | None:
    if arenas is None:
        return None
    ranked = arenas.most_common(2)
    tied = len(ranked) == 2 and ranked[0][1] == ranked[1][1]
    return None if tied or ranked[0][1] < MIN_HOME_ARENA_GAMES else ranked[0][0]


def _unavailable(
    common: Mapping[str, Any], reason: str, inputs: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        **common,
        "status": PREDICTION_UNAVAILABLE,
        "unavailable_reason": reason,
        "home_win_probability": None,
        "away_win_probability": None,
        "favorite": None,
        "inputs": dict(inputs),
    }


def _model_version(session: Session, name: str | None) -> ModelVersion:
    condition = ModelVersion.is_active if name is None else ModelVersion.name == name
    version = session.scalars(select(ModelVersion).where(condition)).one_or_none()
    if version is None:
        if name is not None:
            raise PredictionError(f"{name} is not registered")
        raise PredictionError("no model is active; run: nba-data ml register-model --activate")
    if version.feature_definition_version != FEATURE_DEFINITION_VERSION:
        raise PredictionError(
            f"{version.name} uses {version.feature_definition_version!r}; "
            f"this code computes {FEATURE_DEFINITION_VERSION!r}"
        )
    return version


def _load_model(version: ModelVersion, artifact_dir: Path) -> WinProbabilityModel:
    model, metadata = load_artifact(artifact_dir / version.name)
    if metadata.get("model_sha256") != version.artifact_sha256:
        raise ArtifactIntegrityError(f"{version.name}: the artifact is not the one registered")
    return model


def _schedule(session: Session) -> list[tuple[date, str]]:
    statement = (
        select(Game.game_date, Game.status)
        .join(Season, Season.id == Game.season_id)
        .where(Season.league == "NBA", Game.status != STATUS_POSTPONED)
    )
    return [(row.game_date, row.status) for row in session.execute(statement)]


def _window_games(session: Session, start: date, end: date) -> list[WindowGame]:
    statement = (
        select(
            Game.id,
            Game.basketball_reference_game_id,
            Game.game_date,
            Game.status,
            Game.game_type,
        )
        .join(Season, Season.id == Game.season_id)
        .where(Season.league == "NBA", Game.game_date.between(start, end))
        .order_by(Game.game_date, Game.basketball_reference_game_id)
    )
    return [WindowGame(*row) for row in session.execute(statement)]


def _season_fixtures(session: Session, start: date, end: date) -> list[Fixture]:
    """Every game of each NBA season the window touches."""

    home_ts = aliased(TeamSeason)
    away_ts = aliased(TeamSeason)
    home_team = aliased(Team)
    away_team = aliased(Team)
    seasons = select(Game.season_id).where(Game.game_date.between(start, end))
    statement = (
        select(
            Game.basketball_reference_game_id,
            Season.season_year,
            Game.game_date,
            Game.status,
            Game.game_type,
            Game.neutral_site,
            Game.venue,
            home_team.basketball_reference_team_id,
            away_team.basketball_reference_team_id,
        )
        .join(Season, Season.id == Game.season_id)
        .join(home_ts, home_ts.id == Game.home_team_season_id)
        .join(home_team, home_team.id == home_ts.team_id)
        .join(away_ts, away_ts.id == Game.away_team_season_id)
        .join(away_team, away_team.id == away_ts.team_id)
        .where(Season.league == "NBA", Game.season_id.in_(seasons))
    )
    return [Fixture(*row) for row in session.execute(statement)]


def _games_with_a_row(
    session: Session, model_version_id: int, start: date, end: date, status: str | None = None
) -> set[str]:
    statement = (
        select(Game.basketball_reference_game_id)
        .join(Prediction, Prediction.game_id == Game.id)
        .where(Prediction.model_version_id == model_version_id, Game.game_date.between(start, end))
    )
    if status is not None:
        statement = statement.where(Prediction.status == status)
    return set(session.scalars(statement))


def _load_unfinished_games(session: Session) -> list[TeamGameRecord]:
    """Every game not final, with blank boxes: the schedule the rest features read."""

    home_ts = aliased(TeamSeason)
    away_ts = aliased(TeamSeason)
    home_team = aliased(Team)
    away_team = aliased(Team)
    statement = (
        select(
            Game.basketball_reference_game_id,
            Season.season_year,
            Game.game_date,
            Game.game_type,
            Game.status,
            Game.neutral_site,
            home_team.basketball_reference_team_id,
            away_team.basketball_reference_team_id,
        )
        .join(Season, Season.id == Game.season_id)
        .join(home_ts, home_ts.id == Game.home_team_season_id)
        .join(home_team, home_team.id == home_ts.team_id)
        .join(away_ts, away_ts.id == Game.away_team_season_id)
        .join(away_team, away_team.id == away_ts.team_id)
        .where(Season.league == "NBA", Game.status != STATUS_FINAL)
    )
    return [
        TeamGameRecord(
            game_id=row[0],
            season_year=row[1],
            game_date=row[2],
            game_type=row[3],
            status=row[4],
            neutral_site=row[5],
            home=_blank_box(row[6]),
            away=_blank_box(row[7]),
        )
        for row in session.execute(statement)
    ]


def _blank_box(team_code: str) -> TeamBox:
    return TeamBox(team_code, None, None, None, None, None, None, None, None, None, None)


def _insert(session: Session, rows: Sequence[Mapping[str, Any]]) -> int:
    if not rows:
        return 0
    statement = (
        insert(Prediction)
        .values(list(rows))
        .on_conflict_do_nothing(constraint=_UNIQUE_KEY)
        .returning(Prediction.id)
    )
    return len(session.execute(statement).all())
