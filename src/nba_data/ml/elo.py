"""FiveThirtyEight-form Elo over team codes, in plain Python.

The constants are part of feature definition `team-pregame-v1`; changing one
changes the features and bumps that version. A rating is read before a game and
updated after it, and the caller feeds games in `(game_date, game_id)` order.
"""

from __future__ import annotations

from dataclasses import dataclass

from nba_data.ml.team_games import TeamGameRecord

ELO_START = 1500.0
ELO_K = 20.0
ELO_HOME_ADVANTAGE = 100.0
# Between seasons a rating keeps this share and regresses the rest to the mean.
ELO_SEASON_CARRY = 0.75
ELO_SEASON_MEAN = 1505.0


def home_advantage(neutral_site: bool | None) -> float:
    """Zero only on a known neutral floor; an undetermined venue counts as home."""

    return 0.0 if neutral_site is True else ELO_HOME_ADVANTAGE


def expected_home_win(elo_home: float, elo_away: float, advantage: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-(elo_home + advantage - elo_away) / 400.0))


def margin_multiplier(margin: int, elo_diff_winner: float) -> float:
    """`elo_diff_winner` is the winner's pre-game rating minus the loser's, home advantage included."""

    return (abs(margin) + 3) ** 0.8 / (7.5 + 0.006 * elo_diff_winner)


@dataclass(frozen=True)
class _Rating:
    value: float
    season_year: int


class EloRatings:
    """Every team's rating as of the last game fed to `update`."""

    def __init__(self) -> None:
        self._ratings: dict[str, _Rating] = {}

    def pregame(self, team_code: str, season_year: int) -> float:
        """The rating a team carries into a game of `season_year`.

        A code with no earlier game starts at `ELO_START`. A rating last updated
        in an earlier season regresses once toward `ELO_SEASON_MEAN`, however
        many seasons were skipped.
        """

        rating = self._ratings.get(team_code)
        if rating is None:
            return ELO_START
        if rating.season_year < season_year:
            return ELO_SEASON_CARRY * rating.value + (1 - ELO_SEASON_CARRY) * ELO_SEASON_MEAN
        return rating.value

    def update(self, game: TeamGameRecord) -> None:
        home_pts, away_pts = game.home.pts, game.away.pts
        if home_pts is None or away_pts is None:
            raise ValueError(f"{game.game_id}: Elo needs both final scores")
        margin = home_pts - away_pts
        if margin == 0:
            raise ValueError(f"{game.game_id}: a final NBA game cannot be tied")

        season = game.season_year
        elo_home = self.pregame(game.home.team_code, season)
        elo_away = self.pregame(game.away.team_code, season)
        advantage = home_advantage(game.neutral_site)
        home_diff = elo_home + advantage - elo_away
        elo_diff_winner = home_diff if margin > 0 else -home_diff

        shift = (
            ELO_K
            * margin_multiplier(margin, elo_diff_winner)
            * ((1.0 if margin > 0 else 0.0) - expected_home_win(elo_home, elo_away, advantage))
        )
        self._ratings[game.home.team_code] = _Rating(elo_home + shift, season)
        self._ratings[game.away.team_code] = _Rating(elo_away - shift, season)
