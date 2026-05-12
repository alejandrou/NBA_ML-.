from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nba_data.db.base import Base


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


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        Index("ix_core_teams_bref_id", "basketball_reference_team_id"),
        {"schema": "core"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    basketball_reference_team_id: Mapped[str | None] = mapped_column(String(10))
    current_abbreviation: Mapped[str | None] = mapped_column(String(10))
    current_name: Mapped[str] = mapped_column(String(200), nullable=False)
    franchise_id: Mapped[str | None] = mapped_column(String(100))

    aliases: Mapped[list[TeamAlias]] = relationship(back_populates="team")


class TeamAlias(Base):
    __tablename__ = "team_aliases"
    __table_args__ = (
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
