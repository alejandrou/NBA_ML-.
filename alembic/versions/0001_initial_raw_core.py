"""initial raw and core schemas

Revision ID: 0001_initial_raw_core
Revises:
Create Date: 2026-05-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_raw_core"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS raw")
    op.execute("CREATE SCHEMA IF NOT EXISTS core")

    op.create_table(
        "raw_pages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("cache_path", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("parser_version", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.UniqueConstraint("url", "content_hash", name="uq_raw_pages_url_content_hash"),
        schema="raw",
    )

    op.create_table(
        "scraper_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_type", sa.String(length=100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("config_json", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        schema="raw",
    )

    op.create_table(
        "scraper_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("scraper_run_id", sa.Integer(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["scraper_run_id"], ["raw.scraper_runs.id"]),
        schema="raw",
    )
    op.create_index("ix_raw_scraper_requests_url", "scraper_requests", ["url"], schema="raw")

    op.create_table(
        "seasons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("season_year", sa.Integer(), nullable=False),
        sa.Column("league", sa.String(length=20), nullable=False),
        sa.Column("label", sa.String(length=20), nullable=True),
        sa.UniqueConstraint("league", "season_year", name="uq_core_seasons_league_year"),
        schema="core",
    )

    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("basketball_reference_team_id", sa.String(length=10), nullable=True),
        sa.Column("current_abbreviation", sa.String(length=10), nullable=True),
        sa.Column("current_name", sa.String(length=200), nullable=False),
        sa.Column("franchise_id", sa.String(length=100), nullable=True),
        schema="core",
    )
    op.create_index("ix_core_teams_bref_id", "teams", ["basketball_reference_team_id"], schema="core")

    op.create_table(
        "team_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("abbreviation", sa.String(length=10), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("from_season_year", sa.Integer(), nullable=True),
        sa.Column("to_season_year", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["core.teams.id"]),
        sa.UniqueConstraint(
            "team_id",
            "abbreviation",
            "from_season_year",
            "to_season_year",
            name="uq_core_team_aliases_team_abbrev_range",
        ),
        schema="core",
    )

    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("basketball_reference_player_id", sa.String(length=32), nullable=True),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=True),
        sa.UniqueConstraint("basketball_reference_player_id", name="uq_core_players_bref_id"),
        schema="core",
    )


def downgrade() -> None:
    op.drop_table("players", schema="core")
    op.drop_table("team_aliases", schema="core")
    op.drop_index("ix_core_teams_bref_id", table_name="teams", schema="core")
    op.drop_table("teams", schema="core")
    op.drop_table("seasons", schema="core")
    op.drop_index("ix_raw_scraper_requests_url", table_name="scraper_requests", schema="raw")
    op.drop_table("scraper_requests", schema="raw")
    op.drop_table("scraper_runs", schema="raw")
    op.drop_table("raw_pages", schema="raw")
    op.execute("DROP SCHEMA IF EXISTS core")
    op.execute("DROP SCHEMA IF EXISTS raw")
