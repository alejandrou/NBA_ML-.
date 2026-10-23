from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
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
    constraint_suffix = (
        "pts_id" if table_name.startswith("player_team_postseason_") else "player_team_season_id"
    )
    return (
        ForeignKeyConstraint(
            ["player_team_season_id"],
            ["core.player_team_seasons.id"],
            name=f"fk_stats_{table_name}_{constraint_suffix}",
        ),
        UniqueConstraint(
            "player_team_season_id",
            name=f"uq_stats_{table_name}_{constraint_suffix}",
        ),
        {"schema": "stats"},
    )


def _player_season_table_args(table_name: str) -> tuple[object, object, dict[str, str]]:
    constraint_suffix = "ps_id" if table_name.startswith("player_postseason_") else "player_season_id"
    return (
        ForeignKeyConstraint(
            ["player_season_id"],
            ["core.player_seasons.id"],
            name=f"fk_stats_{table_name}_{constraint_suffix}",
        ),
        UniqueConstraint("player_season_id", name=f"uq_stats_{table_name}_{constraint_suffix}"),
        {"schema": "stats"},
    )


class _PrimaryKeyMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True)


class _TeamStintGrainMixin(_PrimaryKeyMixin):
    player_team_season_id: Mapped[int] = mapped_column(Integer, nullable=False)


class _PlayerSeasonGrainMixin(_PrimaryKeyMixin):
    player_season_id: Mapped[int] = mapped_column(Integer, nullable=False)


class _PlayerSeasonMetadataGrainMixin(_PlayerSeasonGrainMixin):
    source_team_code: Mapped[str | None] = mapped_column(String(10))


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
    _PlayerSeasonMetadataGrainMixin,
    _TotalsColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_totals"
    __table_args__ = _player_season_table_args("player_season_totals")


class PlayerSeasonPerGame(
    _PlayerSeasonMetadataGrainMixin,
    _PerGameColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_per_game"
    __table_args__ = _player_season_table_args("player_season_per_game")


class PlayerSeasonPerMinute(
    _PlayerSeasonMetadataGrainMixin,
    _PerMinuteColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_per_minute"
    __table_args__ = _player_season_table_args("player_season_per_minute")


class PlayerSeasonPerPoss(
    _PlayerSeasonMetadataGrainMixin,
    _PerPossColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_per_poss"
    __table_args__ = _player_season_table_args("player_season_per_poss")


class PlayerSeasonAdvanced(
    _PlayerSeasonMetadataGrainMixin,
    _AdvancedColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_advanced"
    __table_args__ = _player_season_table_args("player_season_advanced")


class PlayerSeasonShooting(
    _PlayerSeasonMetadataGrainMixin,
    _ShootingColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_shooting"
    __table_args__ = _player_season_table_args("player_season_shooting")


class PlayerSeasonAdjShooting(
    _PlayerSeasonMetadataGrainMixin,
    _AdjustedShootingColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_adj_shooting"
    __table_args__ = _player_season_table_args("player_season_adj_shooting")


class PlayerSeasonPbp(
    _PlayerSeasonMetadataGrainMixin,
    _PbpColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_season_pbp"
    __table_args__ = _player_season_table_args("player_season_pbp")


class PlayerPostseasonTotals(
    _PlayerSeasonMetadataGrainMixin,
    _TotalsColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_postseason_totals"
    __table_args__ = _player_season_table_args("player_postseason_totals")


class PlayerPostseasonPerGame(
    _PlayerSeasonMetadataGrainMixin,
    _PerGameColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_postseason_per_game"
    __table_args__ = _player_season_table_args("player_postseason_per_game")


class PlayerPostseasonPerMinute(
    _PlayerSeasonMetadataGrainMixin,
    _PerMinuteColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_postseason_per_minute"
    __table_args__ = _player_season_table_args("player_postseason_per_minute")


class PlayerPostseasonPerPoss(
    _PlayerSeasonMetadataGrainMixin,
    _PerPossColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_postseason_per_poss"
    __table_args__ = _player_season_table_args("player_postseason_per_poss")


class PlayerPostseasonAdvanced(
    _PlayerSeasonMetadataGrainMixin,
    _AdvancedColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_postseason_advanced"
    __table_args__ = _player_season_table_args("player_postseason_advanced")


class PlayerPostseasonShooting(
    _PlayerSeasonMetadataGrainMixin,
    _ShootingColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_postseason_shooting"
    __table_args__ = _player_season_table_args("player_postseason_shooting")


class PlayerPostseasonAdjShooting(
    _PlayerSeasonMetadataGrainMixin,
    _AdjustedShootingColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_postseason_adj_shooting"
    __table_args__ = _player_season_table_args("player_postseason_adj_shooting")


class PlayerPostseasonPbp(
    _PlayerSeasonMetadataGrainMixin,
    _PbpColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_postseason_pbp"
    __table_args__ = _player_season_table_args("player_postseason_pbp")


class PlayerTeamPostseasonTotals(
    _TeamStintGrainMixin,
    _TotalsColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_postseason_totals"
    __table_args__ = _team_stint_table_args("player_team_postseason_totals")


class PlayerTeamPostseasonPerGame(
    _TeamStintGrainMixin,
    _PerGameColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_postseason_per_game"
    __table_args__ = _team_stint_table_args("player_team_postseason_per_game")


class PlayerTeamPostseasonPerMinute(
    _TeamStintGrainMixin,
    _PerMinuteColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_postseason_per_minute"
    __table_args__ = _team_stint_table_args("player_team_postseason_per_minute")


class PlayerTeamPostseasonPerPoss(
    _TeamStintGrainMixin,
    _PerPossColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_postseason_per_poss"
    __table_args__ = _team_stint_table_args("player_team_postseason_per_poss")


class PlayerTeamPostseasonAdvanced(
    _TeamStintGrainMixin,
    _AdvancedColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_postseason_advanced"
    __table_args__ = _team_stint_table_args("player_team_postseason_advanced")


class PlayerTeamPostseasonShooting(
    _TeamStintGrainMixin,
    _ShootingColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_postseason_shooting"
    __table_args__ = _team_stint_table_args("player_team_postseason_shooting")


class PlayerTeamPostseasonAdjShooting(
    _TeamStintGrainMixin,
    _AdjustedShootingColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_postseason_adj_shooting"
    __table_args__ = _team_stint_table_args("player_team_postseason_adj_shooting")


class PlayerTeamPostseasonPbp(
    _TeamStintGrainMixin,
    _PbpColumnsMixin,
    _LineageMixin,
    Base,
):
    __tablename__ = "player_team_postseason_pbp"
    __table_args__ = _team_stint_table_args("player_team_postseason_pbp")


# The check conditions below are frozen as the same literal text in revision
# `0009_games_and_box_scores`; `tests/unit/test_game_models.py` pins the two
# together and the participation values to the box score parser's constants.
# A NULL counter satisfies `>= 0`: a blank is unknown, not negative.
_GAME_COUNTERS_NON_NEGATIVE = (
    "seconds_played >= 0 AND pts >= 0 AND fg >= 0 AND fga >= 0 AND fg3 >= 0 "
    "AND fg3a >= 0 AND ft >= 0 AND fta >= 0 AND orb >= 0 AND drb >= 0 "
    "AND trb >= 0 AND ast >= 0 AND stl >= 0 AND blk >= 0 AND tov >= 0 AND pf >= 0"
)


class _GameCountersMixin:
    """Fourteen of a box score's 15 counting stats; `pts` is declared per table.

    A blank cell is NULL, never zero.
    """

    fg: Mapped[int | None] = mapped_column(Integer)
    fga: Mapped[int | None] = mapped_column(Integer)
    fg3: Mapped[int | None] = mapped_column(Integer)
    fg3a: Mapped[int | None] = mapped_column(Integer)
    ft: Mapped[int | None] = mapped_column(Integer)
    fta: Mapped[int | None] = mapped_column(Integer)
    orb: Mapped[int | None] = mapped_column(Integer)
    drb: Mapped[int | None] = mapped_column(Integer)
    trb: Mapped[int | None] = mapped_column(Integer)
    ast: Mapped[int | None] = mapped_column(Integer)
    stl: Mapped[int | None] = mapped_column(Integer)
    blk: Mapped[int | None] = mapped_column(Integer)
    tov: Mapped[int | None] = mapped_column(Integer)
    pf: Mapped[int | None] = mapped_column(Integer)


class TeamGameTotals(_PrimaryKeyMixin, _GameCountersMixin, _LineageMixin, Base):
    """One team's box score total for one game.

    `pts` is the game's result for this side. `tov` is the team's own total,
    team turnovers included, so it is not the sum of its player rows.
    """

    __tablename__ = "team_game_totals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["game_id"], ["core.games.id"], name="fk_stats_team_game_totals_game_id"
        ),
        ForeignKeyConstraint(
            ["team_season_id"],
            ["core.team_seasons.id"],
            name="fk_stats_team_game_totals_team_season_id",
        ),
        UniqueConstraint("game_id", "team_season_id", name="uq_stats_team_game_totals_game_team"),
        UniqueConstraint("game_id", "is_home", name="uq_stats_team_game_totals_game_side"),
        CheckConstraint(
            _GAME_COUNTERS_NON_NEGATIVE, name="ck_stats_team_game_totals_non_negative"
        ),
        Index("ix_stats_team_game_totals_team_season_id", "team_season_id"),
        {"schema": "stats"},
    )

    game_id: Mapped[int] = mapped_column(Integer, nullable=False)
    team_season_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False)
    seconds_played: Mapped[int] = mapped_column(Integer, nullable=False)
    pts: Mapped[int] = mapped_column(Integer, nullable=False)


class PlayerGameTotals(_PrimaryKeyMixin, _GameCountersMixin, _LineageMixin, Base):
    """One player's line in one game, including the lines of players who sat.

    A line that is not `played` carries no stats at all, so a played line of
    zeros and a "Did Not Play" line are always distinguishable. The player is
    referenced directly, not through `core.player_team_seasons`, because
    inactive-only and current-season players may have no player-season row.
    """

    __tablename__ = "player_game_totals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["game_id", "team_season_id"],
            ["stats.team_game_totals.game_id", "stats.team_game_totals.team_season_id"],
            name="fk_stats_player_game_totals_team_game",
        ),
        UniqueConstraint("game_id", "player_id", name="uq_stats_player_game_totals_game_player"),
        CheckConstraint(
            "participation IN ('played', 'did_not_play', 'did_not_dress', 'not_with_team', "
            "'suspended', 'other_absence', 'inactive')",
            name="ck_stats_player_game_totals_participation",
        ),
        CheckConstraint(
            "participation <> 'played' OR seconds_played IS NOT NULL",
            name="ck_stats_player_game_totals_played_has_seconds",
        ),
        CheckConstraint(
            "participation = 'played' OR (NOT starter AND seconds_played IS NULL "
            "AND fg IS NULL AND fga IS NULL AND fg3 IS NULL AND fg3a IS NULL "
            "AND ft IS NULL AND fta IS NULL AND orb IS NULL AND drb IS NULL "
            "AND trb IS NULL AND ast IS NULL AND stl IS NULL AND blk IS NULL "
            "AND tov IS NULL AND pf IS NULL AND pts IS NULL AND plus_minus IS NULL)",
            name="ck_stats_player_game_totals_absent_line_empty",
        ),
        CheckConstraint(
            _GAME_COUNTERS_NON_NEGATIVE, name="ck_stats_player_game_totals_non_negative"
        ),
        Index("ix_stats_player_game_totals_player_id", "player_id"),
        {"schema": "stats"},
    )

    game_id: Mapped[int] = mapped_column(Integer, nullable=False)
    player_id: Mapped[int] = mapped_column(
        ForeignKey("core.players.id", name="fk_stats_player_game_totals_player_id"),
        nullable=False,
    )
    team_season_id: Mapped[int] = mapped_column(Integer, nullable=False)
    starter: Mapped[bool] = mapped_column(Boolean, nullable=False)
    participation: Mapped[str] = mapped_column(Text, nullable=False)
    # The reason exactly as published ("Did Not Dress", "Inactive", ...).
    participation_reason: Mapped[str | None] = mapped_column(Text)
    seconds_played: Mapped[int | None] = mapped_column(Integer)
    pts: Mapped[int | None] = mapped_column(Integer)
    # NULL when blank, as on a 0:00 line or some Cup finals; may be negative.
    plus_minus: Mapped[int | None] = mapped_column(Integer)


__all__ = [
    "PlayerGameTotals",
    "PlayerSeasonAdjShooting",
    "PlayerSeasonAdvanced",
    "PlayerSeasonPbp",
    "PlayerSeasonPerGame",
    "PlayerSeasonPerMinute",
    "PlayerSeasonPerPoss",
    "PlayerSeasonShooting",
    "PlayerSeasonTotals",
    "PlayerPostseasonAdjShooting",
    "PlayerPostseasonAdvanced",
    "PlayerPostseasonPbp",
    "PlayerPostseasonPerGame",
    "PlayerPostseasonPerMinute",
    "PlayerPostseasonPerPoss",
    "PlayerPostseasonShooting",
    "PlayerPostseasonTotals",
    "PlayerTeamPostseasonAdjShooting",
    "PlayerTeamPostseasonAdvanced",
    "PlayerTeamPostseasonPbp",
    "PlayerTeamPostseasonPerGame",
    "PlayerTeamPostseasonPerMinute",
    "PlayerTeamPostseasonPerPoss",
    "PlayerTeamPostseasonShooting",
    "PlayerTeamPostseasonTotals",
    "PlayerTeamSeasonAdjShooting",
    "PlayerTeamSeasonAdvanced",
    "PlayerTeamSeasonPbp",
    "PlayerTeamSeasonPerGame",
    "PlayerTeamSeasonPerMinute",
    "PlayerTeamSeasonPerPoss",
    "PlayerTeamSeasonRoster",
    "PlayerTeamSeasonShooting",
    "PlayerTeamSeasonTotals",
    "TeamGameTotals",
]
