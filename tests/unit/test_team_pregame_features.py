"""`build_team_features`: the cutoff, leakage, windows, and schedule features of `team-pregame-v1`."""

from __future__ import annotations

import ast
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest

from nba_data.ml.elo import ELO_START, EloRatings
from nba_data.ml.team_features import (
    FEATURE_DEFINITION_VERSION,
    FEATURE_NAMES,
    RESULT_METRICS,
    WINDOWS,
    TeamFeatureRow,
    build_team_features,
)
from nba_data.ml.team_games import TeamBox, TeamGameRecord

ML_PACKAGE = Path(__file__).resolve().parents[2] / "src" / "nba_data" / "ml"


def _box(code: str, pts: int | None, **counters: int | None) -> TeamBox:
    values: dict[str, int | None] = {
        "seconds_played": 14400,
        "fg": 40,
        "fga": 85,
        "fg3": 12,
        "ft": 18,
        "fta": 22,
        "orb": 10,
        "drb": 33,
        "tov": 13,
    }
    values.update(counters)
    return TeamBox(team_code=code, pts=pts, **values)  # type: ignore[arg-type]


def _game(
    day: date,
    home: str,
    away: str,
    home_pts: int | None = 105,
    away_pts: int | None = 100,
    *,
    season: int = 2024,
    game_type: str | None = "regular_season",
    status: str = "final",
    neutral: bool | None = False,
    home_counters: dict[str, int | None] | None = None,
    away_counters: dict[str, int | None] | None = None,
) -> TeamGameRecord:
    return TeamGameRecord(
        game_id=f"{day:%Y%m%d}0{home}",
        season_year=season,
        game_date=day,
        game_type=game_type,
        status=status,
        neutral_site=neutral,
        home=_box(home, home_pts, **(home_counters or {})),
        away=_box(away, away_pts, **(away_counters or {})),
    )


def _row(games: list[TeamGameRecord], target: TeamGameRecord, **kwargs: object) -> TeamFeatureRow:
    build = build_team_features(games, target_ids=[target.game_id], **kwargs)  # type: ignore[arg-type]
    (row,) = build.rows
    return row


def _league() -> tuple[list[TeamGameRecord], TeamGameRecord]:
    """A month of varied games among four teams, then the target AAA v BBB."""

    teams = ("AAA", "BBB", "CCC", "DDD")
    start = date(2024, 1, 1)
    games = []
    for offset in range(30):
        home, away = teams[offset % 4], teams[(offset + 1 + offset // 4) % 4]
        if home == away:
            away = teams[(offset + 2) % 4]
        home_pts = 100 + (offset * 7) % 23
        games.append(
            _game(
                start + timedelta(days=offset),
                home,
                away,
                home_pts,
                home_pts + (-1) ** offset * (1 + (offset * 5) % 13),
                home_counters={"fga": 80 + offset % 9, "orb": 8 + offset % 5},
                away_counters={"tov": 10 + offset % 6, "fta": 18 + offset % 7},
            )
        )
    target = _game(date(2024, 1, 31), "AAA", "BBB", 111, 99)
    return [*games, target], target


# --- contract -------------------------------------------------------------------


def test_every_row_carries_the_versioned_feature_names_in_order() -> None:
    games, target = _league()

    build = build_team_features(games, target_ids=[target.game_id])

    assert build.version == FEATURE_DEFINITION_VERSION == "team-pregame-v1"
    assert list(build.rows[0].values) == list(FEATURE_NAMES)
    assert len(FEATURE_NAMES) == 9 + len(RESULT_METRICS) * len(WINDOWS)


def test_rows_come_back_in_date_order_one_per_target() -> None:
    games, target = _league()
    earlier = games[20]

    build = build_team_features(games, target_ids=[target.game_id, earlier.game_id])

    assert [row.game_id for row in build.rows] == [earlier.game_id, target.game_id]


# --- the cutoff -------------------------------------------------------------------


def test_results_use_only_games_at_least_two_days_before_the_target() -> None:
    games = [
        _game(date(2024, 1, 7), "AAA", "CCC", 110, 90),
        _game(date(2024, 1, 8), "AAA", "DDD", 120, 80),
        _game(date(2024, 1, 9), "AAA", "CCC", 80, 130),
    ]
    target = _game(date(2024, 1, 10), "AAA", "BBB")

    alone = _row([*games, target], target)
    with_away = _row([*games, target, _game(date(2024, 1, 2), "BBB", "DDD", 100, 99)], target)

    assert alone.values["games_in_season_before_home"] == 2
    assert alone.values["games_in_season_before_away"] == 0
    assert alone.values["diff_margin_season"] is None  # BBB has no history yet
    # AAA: (20 + 40) / 2, the 9 January loss not visible yet; BBB: +1.
    assert with_away.values["diff_margin_season"] == 30.0 - 1.0


def test_an_earlier_explicit_cutoff_wins_and_a_later_one_changes_nothing() -> None:
    games = [
        _game(date(2024, 1, 3), "AAA", "CCC", 110, 90),
        _game(date(2024, 1, 6), "AAA", "DDD", 120, 80),
    ]
    target = _game(date(2024, 1, 10), "AAA", "BBB")

    earlier = _row([*games, target], target, cutoff=date(2024, 1, 4))
    later = _row([*games, target], target, cutoff=date(2024, 1, 9))
    default = _row([*games, target], target)

    assert earlier.values["games_in_season_before_home"] == 1
    assert later.values == default.values
    assert default.values["games_in_season_before_home"] == 2


def test_elo_is_the_replay_of_every_scored_game_up_to_the_cutoff() -> None:
    games, target = _league()
    cutoff = target.game_date - timedelta(days=2)
    ratings = EloRatings()
    for game in games:
        if game.game_date <= cutoff:
            ratings.update(game)

    row = _row(games, target)

    assert row.values["elo_home"] == ratings.pregame("AAA", 2024)
    assert row.values["elo_away"] == ratings.pregame("BBB", 2024)
    assert row.values["elo_diff"] == ratings.pregame("AAA", 2024) - ratings.pregame("BBB", 2024)


# --- leakage ----------------------------------------------------------------------


def _with_game(games: list[TeamGameRecord], index: int, **changes: object) -> list[TeamGameRecord]:
    changed = list(games)
    changed[index] = replace(changed[index], **changes)  # type: ignore[arg-type]
    return changed


def _after_cutoff(games: list[TeamGameRecord], target: TeamGameRecord) -> list[int]:
    cutoff = target.game_date - timedelta(days=2)
    return [index for index, game in enumerate(games) if game.game_date > cutoff]


def test_changing_any_result_after_the_cutoff_leaves_every_feature_equal() -> None:
    games, target = _league()
    baseline = _row(games, target)
    later = _after_cutoff(games, target)
    assert len(later) == 2  # BBB on 30 January, and the target itself

    for index in later:
        game = games[index]
        mutations = [
            {"home": replace(game.home, pts=40), "away": replace(game.away, pts=160)},
            {"home": replace(game.home, fga=None, orb=0, tov=40, seconds_played=17400)},
            {"away": replace(game.away, drb=None, fg=1, fg3=0, ft=0)},
            {"neutral_site": None},
        ]
        for changes in mutations:
            mutated = _row(_with_game(games, index, **changes), target)
            assert mutated.values == baseline.values, (game.game_id, changes)
            assert repr(mutated) == repr(baseline)


def test_adding_or_deleting_a_game_after_the_target_leaves_every_feature_equal() -> None:
    games, target = _league()
    baseline = _row(games, target)
    after = [
        _game(date(2024, 2, 1), "BBB", "AAA", 150, 60),
        _game(date(2024, 2, 2), "AAA", "CCC", 90, 140, neutral=None),
    ]

    added = _row([*games, *after], target)
    deleted = _row([*games, *after][:-1], target)

    assert added.values == baseline.values
    assert deleted.values == baseline.values
    assert repr(added) == repr(baseline)


def test_changing_a_game_before_the_cutoff_changes_the_features() -> None:
    games, target = _league()
    baseline = _row(games, target)
    index = next(
        index
        for index, game in enumerate(games)
        if game.game_date <= target.game_date - timedelta(days=2)
        and "AAA" in (game.home.team_code, game.away.team_code)
    )
    game = games[index]

    mutated = _row(
        _with_game(games, index, home=replace(game.home, pts=40), away=replace(game.away, pts=160)),
        target,
    )

    assert mutated.values["elo_home"] != baseline.values["elo_home"]
    assert mutated.values["diff_margin_season"] != baseline.values["diff_margin_season"]


# --- windows ------------------------------------------------------------------------


def test_a_teams_first_game_has_no_results_features_and_no_rest() -> None:
    target = _game(date(2024, 1, 10), "AAA", "BBB")
    other = _game(date(2024, 1, 2), "CCC", "DDD")

    build = build_team_features([other, target], target_ids=[target.game_id])
    values = build.rows[0].values

    for metric in RESULT_METRICS:
        for window, _ in WINDOWS:
            assert values[f"diff_{metric}_{window}"] is None
    assert values["diff_rest_days"] is None
    assert values["diff_back_to_back"] == 0
    assert values["diff_games_last_7_days"] == 0
    assert values["games_in_season_before_home"] == 0
    assert values["elo_home"] == values["elo_away"] == ELO_START


def test_an_early_season_window_uses_the_games_it_has() -> None:
    games = [
        _game(date(2024, 1, 1), "AAA", "CCC", 110, 100),
        _game(date(2024, 1, 3), "DDD", "AAA", 100, 104),
        _game(date(2024, 1, 2), "BBB", "CCC", 101, 100),
    ]
    target = _game(date(2024, 1, 10), "AAA", "BBB")

    values = _row([*games, target], target).values

    # AAA: +10 and +4; BBB: +1.
    for window, _ in WINDOWS:
        assert values[f"diff_margin_{window}"] == 7.0 - 1.0


def test_windows_take_only_the_most_recent_games() -> None:
    start = date(2024, 1, 1)
    games = [
        _game(start + timedelta(days=offset), "AAA", "CCC", 100 + offset, 99)
        for offset in range(25)
    ]
    opponent = _game(date(2024, 1, 2), "BBB", "DDD", 100, 99)
    target = _game(date(2024, 2, 1), "AAA", "BBB")

    values = _row([*games, opponent, target], target).values

    margins = [1 + offset for offset in range(25)]
    assert values["diff_margin_l5"] == sum(margins[-5:]) / 5 - 1
    assert values["diff_margin_l10"] == sum(margins[-10:]) / 10 - 1
    assert values["diff_margin_l20"] == sum(margins[-20:]) / 20 - 1
    assert values["diff_margin_season"] == sum(margins) / 25 - 1


def test_rates_accumulate_numerators_and_denominators() -> None:
    games = [
        _game(date(2024, 1, 1), "AAA", "CCC", home_counters={"fg": 30, "fg3": 0, "fga": 100}),
        _game(date(2024, 1, 2), "AAA", "CCC", home_counters={"fg": 20, "fg3": 0, "fga": 20}),
        _game(date(2024, 1, 3), "BBB", "DDD", home_counters={"fg": 10, "fg3": 0, "fga": 20}),
    ]
    target = _game(date(2024, 1, 10), "AAA", "BBB")

    values = _row([*games, target], target).values

    # 50 / 120, not the mean of 0.3 and 1.0.
    assert values["diff_efg_pct_season"] == pytest.approx(50 / 120 - 0.5, abs=1e-12)


def test_the_four_factors_pace_and_ratings_follow_the_published_formulas() -> None:
    game = _game(
        date(2024, 1, 1),
        "AAA",
        "CCC",
        112,
        98,
        home_counters={"fg": 41, "fga": 88, "fg3": 13, "ft": 17, "fta": 21, "orb": 11, "tov": 12},
        away_counters={"fga": 84, "fta": 25, "orb": 9, "drb": 30, "tov": 15},
    )
    target = _game(date(2024, 1, 10), "AAA", "CCC")

    values = _row([game, target], target).values

    possessions = ((88 + 0.44 * 21 - 11 + 12) + (84 + 0.44 * 25 - 9 + 15)) / 2
    minutes = 14400 / 5 / 60
    home = {
        "off_rtg": 100 * 112 / possessions,
        "def_rtg": 100 * 98 / possessions,
        "net_rtg": 100 * 14 / possessions,
        "pace": 48 * possessions / minutes,
        "margin": 14.0,
        "efg_pct": (41 + 0.5 * 13) / 88,
        "tov_pct": 12 / (88 + 0.44 * 21 + 12),
        "orb_pct": 11 / (11 + 30),
        "ft_rate": 17 / 88,
    }
    away = {
        "off_rtg": 100 * 98 / possessions,
        "def_rtg": 100 * 112 / possessions,
        "net_rtg": -100 * 14 / possessions,
        "pace": 48 * possessions / minutes,
        "margin": -14.0,
        "efg_pct": (40 + 0.5 * 12) / 84,
        "tov_pct": 15 / (84 + 0.44 * 25 + 15),
        "orb_pct": 9 / (9 + 33),
        "ft_rate": 18 / 84,
    }
    for metric in RESULT_METRICS:
        assert values[f"diff_{metric}_season"] == pytest.approx(
            home[metric] - away[metric], abs=1e-9
        ), metric


def test_a_null_counter_is_skipped_by_its_features_and_counted() -> None:
    games = [
        _game(date(2024, 1, 1), "AAA", "CCC", 110, 100, home_counters={"orb": None}),
        _game(date(2024, 1, 2), "AAA", "DDD", 104, 100, home_counters={"orb": 12}),
        _game(date(2024, 1, 3), "BBB", "DDD", 100, 99),
    ]
    target = _game(date(2024, 1, 10), "AAA", "BBB")

    build = build_team_features([*games, target], target_ids=[target.game_id])
    values = build.rows[0].values

    # ORB% uses only the second game for AAA: 12 / (12 + 33); BBB: 10 / 43.
    assert values["diff_orb_pct_season"] == pytest.approx(12 / 45 - 10 / 43, abs=1e-12)
    # Margin needs no rebound, so both games count: (10 + 4) / 2 − 1.
    assert values["diff_margin_season"] == 6.0
    assert build.skipped_games["orb_pct"] == 1
    assert build.skipped_games["off_rtg"] == 1  # possessions need ORB
    assert build.skipped_games["efg_pct"] == 0
    assert build.skipped_games["elo"] == 0


def test_a_window_whose_only_game_lacks_a_counter_gives_none() -> None:
    games = [
        _game(date(2024, 1, 1), "AAA", "CCC", home_counters={"ft": None}),
        _game(date(2024, 1, 2), "BBB", "DDD"),
    ]
    target = _game(date(2024, 1, 10), "AAA", "BBB")

    values = _row([*games, target], target).values

    assert values["diff_ft_rate_season"] is None
    assert values["diff_efg_pct_season"] is not None


def test_a_zero_denominator_gives_none_not_zero() -> None:
    games = [
        _game(date(2024, 1, 1), "AAA", "CCC", home_counters={"fga": 0, "fg": 0, "fg3": 0}),
        _game(date(2024, 1, 2), "BBB", "DDD"),
    ]
    target = _game(date(2024, 1, 10), "AAA", "BBB")

    values = _row([*games, target], target).values

    assert values["diff_efg_pct_season"] is None
    assert values["diff_ft_rate_season"] is None


def test_an_unscored_game_is_skipped_by_elo_and_counted() -> None:
    games = [
        _game(date(2024, 1, 1), "AAA", "CCC", None, 100),
        _game(date(2024, 1, 2), "BBB", "DDD"),
    ]
    target = _game(date(2024, 1, 10), "AAA", "BBB")

    build = build_team_features([*games, target], target_ids=[target.game_id])

    assert build.skipped_games["elo"] == 1
    assert build.skipped_games["margin"] == 1
    assert build.rows[0].values["elo_home"] == ELO_START
    assert build.rows[0].values["games_in_season_before_home"] == 1


def test_skip_counts_cover_all_supplied_history_not_one_targets_cutoff() -> None:
    target = _game(date(2024, 1, 10), "AAA", "BBB")
    later_unscored = _game(date(2024, 2, 1), "AAA", "CCC", None, 100)

    without = build_team_features([target], target_ids=[target.game_id])
    with_later = build_team_features([target, later_unscored], target_ids=[target.game_id])

    assert with_later.rows == without.rows
    assert without.skipped_games["elo"] == 0
    assert with_later.skipped_games["elo"] == 1


def test_windows_reset_each_season_and_elo_carries_over() -> None:
    games = [
        _game(date(2023, 3, 1), "AAA", "CCC", 140, 80, season=2023),
        _game(date(2023, 3, 2), "BBB", "DDD", 100, 99, season=2023),
    ]
    target = _game(date(2023, 11, 1), "AAA", "BBB", season=2024)

    values = _row([*games, target], target).values

    assert values["games_in_season_before_home"] == 0
    assert values["diff_margin_season"] is None
    assert values["diff_rest_days"] is None
    assert values["elo_home"] > ELO_START


# --- schedule features ----------------------------------------------------------------


def test_rest_back_to_back_and_density_cross_a_month_boundary() -> None:
    games = [
        _game(date(2024, 1, 24), "AAA", "CCC"),
        _game(date(2024, 1, 28), "AAA", "DDD"),
        _game(date(2024, 1, 30), "CCC", "AAA"),
        _game(date(2024, 1, 31), "AAA", "DDD"),
        _game(date(2024, 1, 29), "BBB", "CCC"),
    ]
    target = _game(date(2024, 2, 1), "AAA", "BBB")

    values = _row([*games, target], target).values

    # AAA: rest 0, back-to-back, 3 games from 25 to 31 January (not the 24th).
    # BBB: rest 2, no back-to-back, 1 game.
    assert values["diff_rest_days"] == 0 - 2
    assert values["diff_back_to_back"] == 1
    assert values["diff_games_last_7_days"] == 3 - 1


def test_rest_is_capped_at_seven_days() -> None:
    games = [
        _game(date(2024, 1, 1), "AAA", "CCC"),
        _game(date(2024, 1, 20), "BBB", "CCC"),
    ]
    target = _game(date(2024, 1, 30), "AAA", "BBB")

    values = _row([*games, target], target).values

    assert values["diff_rest_days"] == 7 - 7


def test_schedule_features_read_scheduled_games_but_not_postponed_ones() -> None:
    games = [
        _game(date(2024, 1, 9), "AAA", "CCC", None, None, status="scheduled", game_type=None),
        _game(date(2024, 1, 9), "BBB", "DDD", None, None, status="postponed", game_type=None),
        _game(date(2024, 1, 2), "BBB", "CCC"),
    ]
    target = _game(date(2024, 1, 10), "AAA", "BBB", status="scheduled")

    build = build_team_features([*games, target], target_ids=[target.game_id])
    values = build.rows[0].values

    assert values["diff_back_to_back"] == 1
    assert values["games_in_season_before_home"] == 0
    assert build.skipped_games["elo"] == 0


# --- history and targets ----------------------------------------------------------------


def test_a_cup_final_is_history_and_playoffs_are_not() -> None:
    games = [
        _game(date(2024, 1, 1), "AAA", "CCC", 120, 100, game_type="cup_final", neutral=True),
        _game(date(2024, 1, 2), "AAA", "DDD", 120, 100, game_type="playoffs"),
        _game(date(2024, 1, 3), "AAA", "DDD", 120, 100, game_type="play_in"),
        _game(date(2024, 1, 4), "BBB", "DDD"),
    ]
    target = _game(date(2024, 1, 10), "AAA", "BBB")

    values = _row([*games, target], target).values

    assert values["games_in_season_before_home"] == 1


@pytest.mark.parametrize("game_type", ["cup_final", "playoffs", "play_in"])
def test_only_regular_season_games_are_targets(game_type: str) -> None:
    target = _game(date(2024, 1, 10), "AAA", "BBB", game_type=game_type)

    with pytest.raises(ValueError, match="only regular-season"):
        build_team_features([target], target_ids=[target.game_id])


def test_a_scheduled_game_as_stored_is_refused_until_it_is_classified() -> None:
    # `core.games` stores a scheduled game with no competition type.
    target = _game(date(2024, 1, 10), "AAA", "BBB", None, None, status="scheduled", game_type=None)

    with pytest.raises(ValueError, match="no competition type"):
        build_team_features([target], target_ids=[target.game_id])


@pytest.mark.parametrize("game_type", ["regular_season", None])
def test_a_postponed_game_is_never_a_target(game_type: str | None) -> None:
    history = _game(date(2024, 1, 2), "AAA", "CCC")
    target = _game(
        date(2024, 1, 10), "AAA", "BBB", None, None, status="postponed", game_type=game_type
    )

    with pytest.raises(ValueError, match="postponed"):
        build_team_features([history, target], target_ids=[target.game_id])


def test_an_unknown_target_or_a_duplicate_game_is_refused() -> None:
    game = _game(date(2024, 1, 10), "AAA", "BBB")

    with pytest.raises(ValueError, match="not among the games"):
        build_team_features([game], target_ids=["202401100ZZZ"])
    with pytest.raises(ValueError, match="appears twice"):
        build_team_features([game, game], target_ids=[game.game_id])
    with pytest.raises(TypeError):
        build_team_features([game], target_ids=game.game_id)


def test_undetermined_venues_are_treated_as_home_and_counted() -> None:
    games = [
        _game(date(2024, 1, 1), "AAA", "CCC", neutral=None),
        _game(date(2024, 1, 2), "BBB", "DDD", neutral=True),
        _game(date(2024, 1, 9), "AAA", "DDD", neutral=None),  # after the cutoff
    ]
    target = _game(date(2024, 1, 10), "AAA", "BBB", neutral=None)
    neutral_target = _game(date(2024, 1, 12), "CCC", "DDD", neutral=True)

    build = build_team_features(
        [*games, target, neutral_target], target_ids=[target.game_id, neutral_target.game_id]
    )

    # The 1 January game fed Elo; the 10 January game is a target. The 9 January
    # game is before the 12 January target's cutoff, so it fed Elo too.
    assert build.null_neutral_as_home == 3
    assert build.rows[0].values["is_neutral"] is False
    assert build.rows[1].values["is_neutral"] is True


# --- boundaries -------------------------------------------------------------------------


def test_the_ml_package_imports_no_numeric_library() -> None:
    forbidden = {"numpy", "pandas", "sklearn", "scipy"}
    for path in sorted(ML_PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                roots = {(node.module or "").split(".")[0]}
            else:
                continue
            assert not roots & forbidden, f"{path.name} imports {roots & forbidden}"


def test_only_team_games_touches_the_database() -> None:
    for path in sorted(ML_PACKAGE.glob("*.py")):
        if path.name == "team_games.py":
            continue
        source = path.read_text(encoding="utf-8")
        assert "sqlalchemy" not in source, path.name
        assert "nba_data.db" not in source, path.name
