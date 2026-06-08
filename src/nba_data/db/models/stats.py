from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from nba_data.db.base import Base


def _team_stint_table_args(table_name: str) -> tuple[object, object, dict[str, str]]:
    return (
        ForeignKeyConstraint(
            ["player_team_season_id"],
            ["core.player_team_seasons.id"],
            name=f"fk_stats_{table_name}_player_team_season_id",
        ),
        UniqueConstraint(
            "player_team_season_id",
            name=f"uq_stats_{table_name}_player_team_season_id",
        ),
        {"schema": "stats"},
    )


def _player_season_table_args(table_name: str) -> tuple[object, object, dict[str, str]]:
    return (
        ForeignKeyConstraint(
            ["player_season_id"],
            ["core.player_seasons.id"],
            name=f"fk_stats_{table_name}_player_season_id",
        ),
        UniqueConstraint("player_season_id", name=f"uq_stats_{table_name}_player_season_id"),
        {"schema": "stats"},
    )


class _PrimaryKeyMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class _TeamStintGrainMixin(_PrimaryKeyMixin):
    player_team_season_id: Mapped[int] = mapped_column(Integer, nullable=False)


class _PlayerSeasonGrainMixin(_PrimaryKeyMixin):
    player_season_id: Mapped[int] = mapped_column(Integer, nullable=False)


class _LineageMixin:
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    cache_path: Mapped[str] = mapped_column(Text, nullable=False)
    parser_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class _RosterColumnsMixin:
    jersey_number: Mapped[str | None] = mapped_column(String(20))
    player_name: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[str | None] = mapped_column(String(20))
    height: Mapped[str | None] = mapped_column(String(20))
    weight: Mapped[int | None] = mapped_column(Integer)
    birth_date: Mapped[date | None] = mapped_column(Date)
    experience: Mapped[str | None] = mapped_column(String(20))
    college: Mapped[str | None] = mapped_column(String(200))
    country_flag: Mapped[str | None] = mapped_column(String(20))


class _TotalsColumnsMixin:
    rk: Mapped[int | None] = mapped_column(Integer)
    player_name_display: Mapped[str | None] = mapped_column(String(200))
    age: Mapped[int | None] = mapped_column(Integer)
    g: Mapped[int | None] = mapped_column(Integer)
    gs: Mapped[int | None] = mapped_column(Integer)
    mp: Mapped[int | None] = mapped_column(Integer)
    fg: Mapped[int | None] = mapped_column(Integer)
    fga: Mapped[int | None] = mapped_column(Integer)
    fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg3: Mapped[int | None] = mapped_column(Integer)
    fg3a: Mapped[int | None] = mapped_column(Integer)
    fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg2: Mapped[int | None] = mapped_column(Integer)
    fg2a: Mapped[int | None] = mapped_column(Integer)
    fg2_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    efg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ft: Mapped[int | None] = mapped_column(Integer)
    fta: Mapped[int | None] = mapped_column(Integer)
    ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    orb: Mapped[int | None] = mapped_column(Integer)
    drb: Mapped[int | None] = mapped_column(Integer)
    trb: Mapped[int | None] = mapped_column(Integer)
    ast: Mapped[int | None] = mapped_column(Integer)
    stl: Mapped[int | None] = mapped_column(Integer)
    blk: Mapped[int | None] = mapped_column(Integer)
    tov: Mapped[int | None] = mapped_column(Integer)
    pf: Mapped[int | None] = mapped_column(Integer)
    pts: Mapped[int | None] = mapped_column(Integer)
    tpl_dbl: Mapped[int | None] = mapped_column(Integer)
    awards: Mapped[str | None] = mapped_column(String(200))


class _PerGameColumnsMixin:
    rk: Mapped[int | None] = mapped_column(Integer)
    player_name_display: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[str | None] = mapped_column(String(20))
    age: Mapped[int | None] = mapped_column(Integer)
    g: Mapped[int | None] = mapped_column(Integer)
    gs: Mapped[int | None] = mapped_column(Integer)
    mp_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fga_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg3_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg3a_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg2_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg2a_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg2_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    efg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ft_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fta_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    orb_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    drb_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    trb_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ast_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    stl_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    blk_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    tov_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pf_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pts_per_game: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    awards: Mapped[str | None] = mapped_column(String(200))


class _PerMinuteColumnsMixin:
    rk: Mapped[int | None] = mapped_column(Integer)
    player_name_display: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[str | None] = mapped_column(String(20))
    age: Mapped[int | None] = mapped_column(Integer)
    g: Mapped[int | None] = mapped_column(Integer)
    gs: Mapped[int | None] = mapped_column(Integer)
    mp: Mapped[int | None] = mapped_column(Integer)
    fg_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fga_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg3_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg3a_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg2_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg2a_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg2_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    efg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ft_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fta_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    orb_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    drb_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    trb_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ast_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    stl_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    blk_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    tov_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pf_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pts_per_36: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    awards: Mapped[str | None] = mapped_column(String(200))


class _PerPossColumnsMixin:
    rk: Mapped[int | None] = mapped_column(Integer)
    player_name_display: Mapped[str | None] = mapped_column(String(200))
    age: Mapped[int | None] = mapped_column(Integer)
    g: Mapped[int | None] = mapped_column(Integer)
    gs: Mapped[int | None] = mapped_column(Integer)
    mp: Mapped[int | None] = mapped_column(Integer)
    fg_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fga_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg3_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg3a_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg2_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg2a_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg2_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    efg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ft_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fta_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    orb_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    drb_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    trb_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ast_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    stl_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    blk_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    tov_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pf_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pts_per_poss: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ortg: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    drtg: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    awards: Mapped[str | None] = mapped_column(String(200))


class _AdvancedColumnsMixin:
    rk: Mapped[int | None] = mapped_column(Integer)
    player_name_display: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[str | None] = mapped_column(String(20))
    age: Mapped[int | None] = mapped_column(Integer)
    g: Mapped[int | None] = mapped_column(Integer)
    gs: Mapped[int | None] = mapped_column(Integer)
    mp: Mapped[int | None] = mapped_column(Integer)
    per: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ts_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg3a_per_fga_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fta_per_fga_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    orb_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    drb_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    trb_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ast_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    stl_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    blk_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    tov_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    usg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ows: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    dws: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ws: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ws_per_48: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    obpm: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    dbpm: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    bpm: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    vorp: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    awards: Mapped[str | None] = mapped_column(String(200))


class _ShootingColumnsMixin:
    rk: Mapped[int | None] = mapped_column(Integer)
    player_name_display: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[str | None] = mapped_column(String(20))
    age: Mapped[int | None] = mapped_column(Integer)
    g: Mapped[int | None] = mapped_column(Integer)
    gs: Mapped[int | None] = mapped_column(Integer)
    mp: Mapped[int | None] = mapped_column(Integer)
    fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    avg_dist: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pct_fga_fg2a: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pct_fga_0_3: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pct_fga_3_10: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pct_fga_10_16: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pct_fga_16_plus: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pct_fga_fg3a: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg_pct_fg2a: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg_pct_0_3: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg_pct_3_10: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg_pct_10_16: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg_pct_16_plus: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg_pct_fg3a: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pct_ast_fg2: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pct_ast_fg3: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pct_fga_dunk: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    dunks_made: Mapped[int | None] = mapped_column(Integer)
    pct_fg3a_corner3: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg_pct_corner3: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    heaves_made: Mapped[int | None] = mapped_column(Integer)
    heaves_att: Mapped[int | None] = mapped_column(Integer)
    awards: Mapped[str | None] = mapped_column(String(200))


class _AdjustedShootingColumnsMixin:
    rk: Mapped[int | None] = mapped_column(Integer)
    player_name_display: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[str | None] = mapped_column(String(20))
    age: Mapped[int | None] = mapped_column(Integer)
    g: Mapped[int | None] = mapped_column(Integer)
    gs: Mapped[int | None] = mapped_column(Integer)
    mp: Mapped[int | None] = mapped_column(Integer)
    fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    adj_fg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg2_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    adj_fg2_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    adj_fg3_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    efg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    adj_efg_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    adj_ft_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ts_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    adj_ts_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg3a_per_fga_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    adj_fg3a_per_fga_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fta_per_fga_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    adj_fta_per_fga_pct: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    fg_pts_added: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ts_pts_added: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    awards: Mapped[str | None] = mapped_column(String(200))


class _PbpColumnsMixin:
    rk: Mapped[int | None] = mapped_column(Integer)
    player_name_display: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[str | None] = mapped_column(String(20))
    age: Mapped[int | None] = mapped_column(Integer)
    g: Mapped[int | None] = mapped_column(Integer)
    gs: Mapped[int | None] = mapped_column(Integer)
    mp: Mapped[int | None] = mapped_column(Integer)
    pct_pg: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pct_sg: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pct_sf: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pct_pf: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    pct_c: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    on_court_plus_minus: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    net_plus_minus: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    bad_pass_turnover: Mapped[int | None] = mapped_column(Integer)
    lost_ball_turnover: Mapped[int | None] = mapped_column(Integer)
    fouls_shooting: Mapped[int | None] = mapped_column(Integer)
    fouls_offensive: Mapped[int | None] = mapped_column(Integer)
    drawn_shooting: Mapped[int | None] = mapped_column(Integer)
    drawn_offensive: Mapped[int | None] = mapped_column(Integer)
    and1s: Mapped[int | None] = mapped_column(Integer)
    own_shots_blocked: Mapped[int | None] = mapped_column(Integer)
    assisted_points: Mapped[int | None] = mapped_column(Integer)
    awards: Mapped[str | None] = mapped_column(String(200))


class PlayerTeamSeasonRoster(
    _TeamStintGrainMixin,
    _RosterColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_season_roster"
    __table_args__ = _team_stint_table_args("player_team_season_roster")


class PlayerTeamSeasonTotals(
    _TeamStintGrainMixin,
    _TotalsColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_season_totals"
    __table_args__ = _team_stint_table_args("player_team_season_totals")


class PlayerTeamSeasonPerGame(
    _TeamStintGrainMixin,
    _PerGameColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_season_per_game"
    __table_args__ = _team_stint_table_args("player_team_season_per_game")


class PlayerTeamSeasonPerMinute(
    _TeamStintGrainMixin,
    _PerMinuteColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_season_per_minute"
    __table_args__ = _team_stint_table_args("player_team_season_per_minute")


class PlayerTeamSeasonPerPoss(
    _TeamStintGrainMixin,
    _PerPossColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_season_per_poss"
    __table_args__ = _team_stint_table_args("player_team_season_per_poss")


class PlayerTeamSeasonAdvanced(
    _TeamStintGrainMixin,
    _AdvancedColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_season_advanced"
    __table_args__ = _team_stint_table_args("player_team_season_advanced")


class PlayerTeamSeasonShooting(
    _TeamStintGrainMixin,
    _ShootingColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_season_shooting"
    __table_args__ = _team_stint_table_args("player_team_season_shooting")


class PlayerTeamSeasonAdjShooting(
    _TeamStintGrainMixin,
    _AdjustedShootingColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_season_adj_shooting"
    __table_args__ = _team_stint_table_args("player_team_season_adj_shooting")


class PlayerTeamSeasonPbp(
    _TeamStintGrainMixin,
    _PbpColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_season_pbp"
    __table_args__ = _team_stint_table_args("player_team_season_pbp")


class PlayerSeasonTotals(
    _PlayerSeasonGrainMixin,
    _TotalsColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_totals"
    __table_args__ = _player_season_table_args("player_season_totals")


class PlayerSeasonPerGame(
    _PlayerSeasonGrainMixin,
    _PerGameColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_per_game"
    __table_args__ = _player_season_table_args("player_season_per_game")


class PlayerSeasonPerMinute(
    _PlayerSeasonGrainMixin,
    _PerMinuteColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_per_minute"
    __table_args__ = _player_season_table_args("player_season_per_minute")


class PlayerSeasonPerPoss(
    _PlayerSeasonGrainMixin,
    _PerPossColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_per_poss"
    __table_args__ = _player_season_table_args("player_season_per_poss")


class PlayerSeasonAdvanced(
    _PlayerSeasonGrainMixin,
    _AdvancedColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_advanced"
    __table_args__ = _player_season_table_args("player_season_advanced")


class PlayerSeasonShooting(
    _PlayerSeasonGrainMixin,
    _ShootingColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_shooting"
    __table_args__ = _player_season_table_args("player_season_shooting")


class PlayerSeasonAdjShooting(
    _PlayerSeasonGrainMixin,
    _AdjustedShootingColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_adj_shooting"
    __table_args__ = _player_season_table_args("player_season_adj_shooting")


class PlayerSeasonPbp(
    _PlayerSeasonGrainMixin,
    _PbpColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_pbp"
    __table_args__ = _player_season_table_args("player_season_pbp")


__all__ = [
    "PlayerSeasonAdjShooting",
    "PlayerSeasonAdvanced",
    "PlayerSeasonPbp",
    "PlayerSeasonPerGame",
    "PlayerSeasonPerMinute",
    "PlayerSeasonPerPoss",
    "PlayerSeasonShooting",
    "PlayerSeasonTotals",
    "PlayerTeamSeasonAdjShooting",
    "PlayerTeamSeasonAdvanced",
    "PlayerTeamSeasonPbp",
    "PlayerTeamSeasonPerGame",
    "PlayerTeamSeasonPerMinute",
    "PlayerTeamSeasonPerPoss",
    "PlayerTeamSeasonRoster",
    "PlayerTeamSeasonShooting",
    "PlayerTeamSeasonTotals",
]
