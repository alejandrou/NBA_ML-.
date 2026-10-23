from __future__ import annotations

from datetime import date, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nba_data.db.base import Base
from nba_data.domain.team_codes import reject_synthetic_team_code_sql


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("league", "season_year", name="uq_core_seasons_league_year"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_year: Mapped[int] = mapped_column(Integer, nullable=False)
    league: Mapped[str] = mapped_column(String(20), nullable=False, default="NBA")
    label: Mapped[str | None] = mapped_column(String(20))

    team_seasons: Mapped[list[TeamSeason]] = relationship(back_populates="season")
    player_seasons: Mapped[list[PlayerSeason]] = relationship(back_populates="season")


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("basketball_reference_team_id", name="uq_core_teams_bref_id"),
        CheckConstraint(
            reject_synthetic_team_code_sql("basketball_reference_team_id", nullable=True),
            name="ck_core_teams_bref_id_not_synthetic",
        ),
        CheckConstraint(
            reject_synthetic_team_code_sql("current_abbreviation", nullable=True),
            name="ck_core_teams_current_abbreviation_not_synthetic",
        ),
        Index("ix_core_teams_bref_id", "basketball_reference_team_id"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    basketball_reference_team_id: Mapped[str] = mapped_column(String(10), nullable=False)
    current_abbreviation: Mapped[str | None] = mapped_column(String(10))
    current_name: Mapped[str] = mapped_column(String(200), nullable=False)
    franchise_id: Mapped[str | None] = mapped_column(String(100))

    aliases: Mapped[list[TeamAlias]] = relationship(back_populates="team")
    team_seasons: Mapped[list[TeamSeason]] = relationship(back_populates="team")


class TeamAlias(Base):
    __tablename__ = "team_aliases"
    __table_args__ = (
        CheckConstraint(
            reject_synthetic_team_code_sql("abbreviation", nullable=False),
            name="ck_core_team_aliases_abbreviation_not_synthetic",
        ),
        UniqueConstraint(
            "team_id",
            "abbreviation",
            "from_season_year",
            "to_season_year",
            name="uq_core_team_aliases_team_abbrev_range",
        ),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("core.teams.id"), nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    from_season_year: Mapped[int | None] = mapped_column(Integer)
    to_season_year: Mapped[int | None] = mapped_column(Integer)

    team: Mapped[Team] = relationship(back_populates="aliases")


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        UniqueConstraint("basketball_reference_player_id", name="uq_core_players_bref_id"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    basketball_reference_player_id: Mapped[str | None] = mapped_column(String(32))
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str | None] = mapped_column(String(200))

    player_seasons: Mapped[list[PlayerSeason]] = relationship(back_populates="player")


class TeamSeason(Base):
    __tablename__ = "team_seasons"
    __table_args__ = (
        UniqueConstraint("team_id", "season_id", name="uq_core_team_seasons_team_season"),
        UniqueConstraint(
            "season_id",
            "team_abbreviation",
            name="uq_core_team_seasons_season_abbrev",
        ),
        # The target of `core.games`' composite keys, which hold both of a
        # game's teams to the game's own season. `id` alone is already unique.
        UniqueConstraint("id", "season_id", name="uq_core_team_seasons_id_season"),
        CheckConstraint(
            reject_synthetic_team_code_sql("team_abbreviation", nullable=False),
            name="ck_core_team_seasons_abbrev_not_synthetic",
        ),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("core.teams.id"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("core.seasons.id"), nullable=False)
    team_abbreviation: Mapped[str] = mapped_column(String(10), nullable=False)

    team: Mapped[Team] = relationship(back_populates="team_seasons")
    season: Mapped[Season] = relationship(back_populates="team_seasons")
    player_team_seasons: Mapped[list[PlayerTeamSeason]] = relationship(
        back_populates="team_season"
    )


class PlayerSeason(Base):
    __tablename__ = "player_seasons"
    __table_args__ = (
        UniqueConstraint("player_id", "season_id", name="uq_core_player_seasons_player_season"),
        Index("ix_core_player_seasons_season_id", "season_id"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("core.players.id"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("core.seasons.id"), nullable=False)

    player: Mapped[Player] = relationship(back_populates="player_seasons")
    season: Mapped[Season] = relationship(back_populates="player_seasons")
    player_team_seasons: Mapped[list[PlayerTeamSeason]] = relationship(
        back_populates="player_season"
    )


class PlayerTeamSeason(Base):
    __tablename__ = "player_team_seasons"
    __table_args__ = (
        UniqueConstraint(
            "player_season_id",
            "team_season_id",
            name="uq_core_player_team_seasons_player_team",
        ),
        Index("ix_core_player_team_seasons_team_season_id", "team_season_id"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_season_id: Mapped[int] = mapped_column(
        ForeignKey("core.player_seasons.id"), nullable=False
    )
    team_season_id: Mapped[int] = mapped_column(ForeignKey("core.team_seasons.id"), nullable=False)
    roster_number: Mapped[str | None] = mapped_column(String(20))
    roster_position: Mapped[str | None] = mapped_column(String(50))

    player_season: Mapped[PlayerSeason] = relationship(back_populates="player_team_seasons")
    team_season: Mapped[TeamSeason] = relationship(back_populates="player_team_seasons")


class Game(Base):
    """One game's identity, schedule, and status — never its result.

    The final score is `stats.team_game_totals.pts`, stored once. The check
    conditions are frozen as the same literal text in revision
    `0009_games_and_box_scores`; `tests/unit/test_game_models.py` pins the two
    together and the allowed values to the box score parser's constants.
    """

    __tablename__ = "games"
    __table_args__ = (
        UniqueConstraint("basketball_reference_game_id", name="uq_core_games_bref_id"),
        CheckConstraint(
            "basketball_reference_game_id ~ '^[0-9]{8}0[A-Z]{3}$'",
            name="ck_core_games_bref_id_format",
        ),
        CheckConstraint(
            "home_team_season_id <> away_team_season_id",
            name="ck_core_games_distinct_teams",
        ),
        CheckConstraint(
            "game_type IN ('regular_season', 'play_in', 'playoffs', 'cup_final')",
            name="ck_core_games_game_type",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'final', 'postponed')",
            name="ck_core_games_status",
        ),
        CheckConstraint(
            "status <> 'final' OR game_type IS NOT NULL",
            name="ck_core_games_final_has_game_type",
        ),
        CheckConstraint("attendance >= 0", name="ck_core_games_attendance_non_negative"),
        ForeignKeyConstraint(
            ["home_team_season_id", "season_id"],
            ["core.team_seasons.id", "core.team_seasons.season_id"],
            name="fk_core_games_home_team_season",
        ),
        ForeignKeyConstraint(
            ["away_team_season_id", "season_id"],
            ["core.team_seasons.id", "core.team_seasons.season_id"],
            name="fk_core_games_away_team_season",
        ),
        Index("ix_core_games_home_team_season_date", "home_team_season_id", "game_date"),
        Index("ix_core_games_away_team_season_date", "away_team_season_id", "game_date"),
        Index("ix_core_games_game_date", "game_date"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    basketball_reference_game_id: Mapped[str] = mapped_column(Text, nullable=False)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("core.seasons.id", name="fk_core_games_season_id"), nullable=False
    )
    home_team_season_id: Mapped[int] = mapped_column(Integer, nullable=False)
    away_team_season_id: Mapped[int] = mapped_column(Integer, nullable=False)
    game_date: Mapped[date] = mapped_column(Date, nullable=False)
    # As published, US Eastern; never converted to a timestamp here.
    start_time_et: Mapped[time | None] = mapped_column(Time)
    game_type: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    venue: Mapped[str | None] = mapped_column(Text)
    # NULL means not determined; it never defaults to false.
    neutral_site: Mapped[bool | None] = mapped_column(Boolean)
    # NULL is a blank on the page; 0 is a published zero.
    attendance: Mapped[int | None] = mapped_column(Integer)
