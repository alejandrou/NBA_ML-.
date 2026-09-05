"""Drop the unused raw schema.

Revision ID: 0008_drop_raw_schema
Revises: 0007_team_bref_id_not_null
Create Date: 2026-09-05 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_drop_raw_schema"
down_revision: str | None = "0007_team_bref_id_not_null"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_raw_scraper_requests_url", table_name="scraper_requests", schema="raw")
    op.drop_table("scraper_requests", schema="raw")
    op.drop_table("scraper_runs", schema="raw")
    op.drop_table("raw_pages", schema="raw")
    op.execute("DROP SCHEMA IF EXISTS raw")


def downgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS raw")

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
