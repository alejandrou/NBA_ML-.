from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nba_data.db.base import Base


class RawPage(Base):
    __tablename__ = "raw_pages"
    __table_args__ = (
        UniqueConstraint("url", "content_hash", name="uq_raw_pages_url_content_hash"),
        {"schema": "raw"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="basketball-reference")
    cache_path: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    parser_version: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="fetched")
    error: Mapped[str | None] = mapped_column(Text)


class ScraperRun(Base):
    __tablename__ = "scraper_runs"
    __table_args__ = {"schema": "raw"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="started")
    config_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)

    requests: Mapped[list[ScraperRequest]] = relationship(back_populates="scraper_run")


class ScraperRequest(Base):
    __tablename__ = "scraper_requests"
    __table_args__ = (
        Index("ix_raw_scraper_requests_url", "url"),
        {"schema": "raw"},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scraper_run_id: Mapped[int | None] = mapped_column(ForeignKey("raw.scraper_runs.id"))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    cache_hit: Mapped[bool] = mapped_column(default=False, nullable=False)
    requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    error: Mapped[str | None] = mapped_column(Text)

    scraper_run: Mapped[ScraperRun | None] = relationship(back_populates="requests")
