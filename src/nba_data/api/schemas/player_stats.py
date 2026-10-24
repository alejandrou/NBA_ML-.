"""Public bodies of the statistics routes.

Every stat column is the stored name, verbatim and nullable: a missing stat is
`null`, never `0` and never an omitted key. All four dimensions share the same
eight column mixins, so one body per family and grain serves both season types.
`tests/unit/test_player_stats_api.py` holds each body to its mapped tables.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from nba_data.api.schemas.common import ApiDecimal
from nba_data.domain.stat_dimensions import SeasonType, StatFamily

StintT = TypeVar("StintT", bound=BaseModel)


class AggregateStatIdentity(BaseModel):
    season_year: int
    season_type: SeasonType
    source_team_code: str | None
    is_multi_team: bool


class StintStatIdentity(BaseModel):
    season_year: int
    season_type: SeasonType
    basketball_reference_team_id: str


class StintStatListResponse(BaseModel, Generic[StintT]):
    items: list[StintT]
    page: int
    page_size: int
    total: int


class TotalsStats(BaseModel):
    rk: int | None
    age: int | None
    g: int | None
    gs: int | None
    mp: int | None
    fg: int | None
    fga: int | None
    fg_pct: ApiDecimal | None
    fg3: int | None
    fg3a: int | None
    fg3_pct: ApiDecimal | None
    fg2: int | None
    fg2a: int | None
    fg2_pct: ApiDecimal | None
    efg_pct: ApiDecimal | None
    ft: int | None
    fta: int | None
    ft_pct: ApiDecimal | None
    orb: int | None
    drb: int | None
    trb: int | None
    ast: int | None
    stl: int | None
    blk: int | None
    tov: int | None
    pf: int | None
    pts: int | None
    tpl_dbl: int | None
    awards: str | None


class PerGameStats(BaseModel):
    rk: int | None
    position: str | None
    age: int | None
    g: int | None
    gs: int | None
    mp_per_game: ApiDecimal | None
    fg_per_game: ApiDecimal | None
    fga_per_game: ApiDecimal | None
    fg_pct: ApiDecimal | None
    fg3_per_game: ApiDecimal | None
    fg3a_per_game: ApiDecimal | None
    fg3_pct: ApiDecimal | None
    fg2_per_game: ApiDecimal | None
    fg2a_per_game: ApiDecimal | None
    fg2_pct: ApiDecimal | None
    efg_pct: ApiDecimal | None
    ft_per_game: ApiDecimal | None
    fta_per_game: ApiDecimal | None
    ft_pct: ApiDecimal | None
    orb_per_game: ApiDecimal | None
    drb_per_game: ApiDecimal | None
    trb_per_game: ApiDecimal | None
    ast_per_game: ApiDecimal | None
    stl_per_game: ApiDecimal | None
    blk_per_game: ApiDecimal | None
    tov_per_game: ApiDecimal | None
    pf_per_game: ApiDecimal | None
    pts_per_game: ApiDecimal | None
    awards: str | None


class PerMinuteStats(BaseModel):
    rk: int | None
    position: str | None
    age: int | None
    g: int | None
    gs: int | None
    mp: int | None
    fg_per_36: ApiDecimal | None
    fga_per_36: ApiDecimal | None
    fg_pct: ApiDecimal | None
    fg3_per_36: ApiDecimal | None
    fg3a_per_36: ApiDecimal | None
    fg3_pct: ApiDecimal | None
    fg2_per_36: ApiDecimal | None
    fg2a_per_36: ApiDecimal | None
    fg2_pct: ApiDecimal | None
    efg_pct: ApiDecimal | None
    ft_per_36: ApiDecimal | None
    fta_per_36: ApiDecimal | None
    ft_pct: ApiDecimal | None
    orb_per_36: ApiDecimal | None
    drb_per_36: ApiDecimal | None
    trb_per_36: ApiDecimal | None
    ast_per_36: ApiDecimal | None
    stl_per_36: ApiDecimal | None
    blk_per_36: ApiDecimal | None
    tov_per_36: ApiDecimal | None
    pf_per_36: ApiDecimal | None
    pts_per_36: ApiDecimal | None
    awards: str | None


class PerPossStats(BaseModel):
    rk: int | None
    age: int | None
    g: int | None
    gs: int | None
    mp: int | None
    fg_per_poss: ApiDecimal | None
    fga_per_poss: ApiDecimal | None
    fg_pct: ApiDecimal | None
    fg3_per_poss: ApiDecimal | None
    fg3a_per_poss: ApiDecimal | None
    fg3_pct: ApiDecimal | None
    fg2_per_poss: ApiDecimal | None
    fg2a_per_poss: ApiDecimal | None
    fg2_pct: ApiDecimal | None
    efg_pct: ApiDecimal | None
    ft_per_poss: ApiDecimal | None
    fta_per_poss: ApiDecimal | None
    ft_pct: ApiDecimal | None
    orb_per_poss: ApiDecimal | None
    drb_per_poss: ApiDecimal | None
    trb_per_poss: ApiDecimal | None
    ast_per_poss: ApiDecimal | None
    stl_per_poss: ApiDecimal | None
    blk_per_poss: ApiDecimal | None
    tov_per_poss: ApiDecimal | None
    pf_per_poss: ApiDecimal | None
    pts_per_poss: ApiDecimal | None
    ortg: ApiDecimal | None
    drtg: ApiDecimal | None
    awards: str | None


class AdvancedStats(BaseModel):
    rk: int | None
    position: str | None
    age: int | None
    g: int | None
    gs: int | None
    mp: int | None
    per: ApiDecimal | None
    ts_pct: ApiDecimal | None
    fg3a_per_fga_pct: ApiDecimal | None
    fta_per_fga_pct: ApiDecimal | None
    orb_pct: ApiDecimal | None
    drb_pct: ApiDecimal | None
    trb_pct: ApiDecimal | None
    ast_pct: ApiDecimal | None
    stl_pct: ApiDecimal | None
    blk_pct: ApiDecimal | None
    tov_pct: ApiDecimal | None
    usg_pct: ApiDecimal | None
    ows: ApiDecimal | None
    dws: ApiDecimal | None
    ws: ApiDecimal | None
    ws_per_48: ApiDecimal | None
    obpm: ApiDecimal | None
    dbpm: ApiDecimal | None
    bpm: ApiDecimal | None
    vorp: ApiDecimal | None
    awards: str | None


class ShootingStats(BaseModel):
    rk: int | None
    position: str | None
    age: int | None
    g: int | None
    gs: int | None
    mp: int | None
    fg_pct: ApiDecimal | None
    avg_dist: ApiDecimal | None
    pct_fga_fg2a: ApiDecimal | None
    pct_fga_0_3: ApiDecimal | None
    pct_fga_3_10: ApiDecimal | None
    pct_fga_10_16: ApiDecimal | None
    pct_fga_16_plus: ApiDecimal | None
    pct_fga_fg3a: ApiDecimal | None
    fg_pct_fg2a: ApiDecimal | None
    fg_pct_0_3: ApiDecimal | None
    fg_pct_3_10: ApiDecimal | None
    fg_pct_10_16: ApiDecimal | None
    fg_pct_16_plus: ApiDecimal | None
    fg_pct_fg3a: ApiDecimal | None
    pct_ast_fg2: ApiDecimal | None
    pct_ast_fg3: ApiDecimal | None
    pct_fga_dunk: ApiDecimal | None
    dunks_made: int | None
    pct_fg3a_corner3: ApiDecimal | None
    fg_pct_corner3: ApiDecimal | None
    heaves_made: int | None
    heaves_att: int | None
    awards: str | None


class AdjShootingStats(BaseModel):
    rk: int | None
    position: str | None
    age: int | None
    g: int | None
    gs: int | None
    mp: int | None
    fg_pct: ApiDecimal | None
    adj_fg_pct: ApiDecimal | None
    fg2_pct: ApiDecimal | None
    adj_fg2_pct: ApiDecimal | None
    fg3_pct: ApiDecimal | None
    adj_fg3_pct: ApiDecimal | None
    efg_pct: ApiDecimal | None
    adj_efg_pct: ApiDecimal | None
    ft_pct: ApiDecimal | None
    adj_ft_pct: ApiDecimal | None
    ts_pct: ApiDecimal | None
    adj_ts_pct: ApiDecimal | None
    fg3a_per_fga_pct: ApiDecimal | None
    adj_fg3a_per_fga_pct: ApiDecimal | None
    fta_per_fga_pct: ApiDecimal | None
    adj_fta_per_fga_pct: ApiDecimal | None
    fg_pts_added: ApiDecimal | None
    ts_pts_added: ApiDecimal | None
    awards: str | None


class PbpStats(BaseModel):
    rk: int | None
    position: str | None
    age: int | None
    g: int | None
    gs: int | None
    mp: int | None
    pct_pg: ApiDecimal | None
    pct_sg: ApiDecimal | None
    pct_sf: ApiDecimal | None
    pct_pf: ApiDecimal | None
    pct_c: ApiDecimal | None
    on_court_plus_minus: ApiDecimal | None
    net_plus_minus: ApiDecimal | None
    bad_pass_turnover: int | None
    lost_ball_turnover: int | None
    fouls_shooting: int | None
    fouls_offensive: int | None
    drawn_shooting: int | None
    drawn_offensive: int | None
    and1s: int | None
    own_shots_blocked: int | None
    assisted_points: int | None
    awards: str | None


# Each body lists its identity before its stats: Pydantic orders the fields of
# the last base first.
class TotalsAggregateResponse(TotalsStats, AggregateStatIdentity):
    pass


class TotalsStintResponse(TotalsStats, StintStatIdentity):
    pass


class TotalsStintListResponse(StintStatListResponse[TotalsStintResponse]):
    pass


class PerGameAggregateResponse(PerGameStats, AggregateStatIdentity):
    pass


class PerGameStintResponse(PerGameStats, StintStatIdentity):
    pass


class PerGameStintListResponse(StintStatListResponse[PerGameStintResponse]):
    pass


class PerMinuteAggregateResponse(PerMinuteStats, AggregateStatIdentity):
    pass


class PerMinuteStintResponse(PerMinuteStats, StintStatIdentity):
    pass


class PerMinuteStintListResponse(StintStatListResponse[PerMinuteStintResponse]):
    pass


class PerPossAggregateResponse(PerPossStats, AggregateStatIdentity):
    pass


class PerPossStintResponse(PerPossStats, StintStatIdentity):
    pass


class PerPossStintListResponse(StintStatListResponse[PerPossStintResponse]):
    pass


class AdvancedAggregateResponse(AdvancedStats, AggregateStatIdentity):
    pass


class AdvancedStintResponse(AdvancedStats, StintStatIdentity):
    pass


class AdvancedStintListResponse(StintStatListResponse[AdvancedStintResponse]):
    pass


class ShootingAggregateResponse(ShootingStats, AggregateStatIdentity):
    pass


class ShootingStintResponse(ShootingStats, StintStatIdentity):
    pass


class ShootingStintListResponse(StintStatListResponse[ShootingStintResponse]):
    pass


class AdjShootingAggregateResponse(AdjShootingStats, AggregateStatIdentity):
    pass


class AdjShootingStintResponse(AdjShootingStats, StintStatIdentity):
    pass


class AdjShootingStintListResponse(StintStatListResponse[AdjShootingStintResponse]):
    pass


class PbpAggregateResponse(PbpStats, AggregateStatIdentity):
    pass


class PbpStintResponse(PbpStats, StintStatIdentity):
    pass


class PbpStintListResponse(StintStatListResponse[PbpStintResponse]):
    pass


# One aggregate body and one stint collection per family, for every season type.
STAT_BODIES: dict[
    StatFamily, tuple[type[AggregateStatIdentity], type[StintStatListResponse[Any]]]
] = {
    StatFamily.TOTALS: (TotalsAggregateResponse, TotalsStintListResponse),
    StatFamily.PER_GAME: (PerGameAggregateResponse, PerGameStintListResponse),
    StatFamily.PER_MINUTE: (PerMinuteAggregateResponse, PerMinuteStintListResponse),
    StatFamily.PER_POSS: (PerPossAggregateResponse, PerPossStintListResponse),
    StatFamily.ADVANCED: (AdvancedAggregateResponse, AdvancedStintListResponse),
    StatFamily.SHOOTING: (ShootingAggregateResponse, ShootingStintListResponse),
    StatFamily.ADJ_SHOOTING: (AdjShootingAggregateResponse, AdjShootingStintListResponse),
    StatFamily.PBP: (PbpAggregateResponse, PbpStintListResponse),
}
