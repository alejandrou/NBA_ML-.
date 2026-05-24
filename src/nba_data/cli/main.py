from pathlib import Path

import typer
from rich.console import Console

from nba_data import __version__
from nba_data.config.settings import get_settings
from nba_data.scraping.backfill_manifest import (
    ManifestValidationError,
    dry_run_backfill_manifest,
)
from nba_data.scraping.cache import HtmlCache

app = typer.Typer(help="Safe local utilities for the NBA data platform.")
cache_app = typer.Typer(help="HTML cache utilities.")
backfill_app = typer.Typer(help="Controlled raw HTML backfill utilities.")
app.add_typer(cache_app, name="cache")
app.add_typer(backfill_app, name="backfill")
console = Console()


@app.command()
def info() -> None:
    """Show project information."""

    console.print(f"nba-data-platform {__version__}")
    console.print("Phase 1 foundation CLI. No live scraping commands are enabled.")


@app.command("settings")
def show_settings() -> None:
    """Show non-secret runtime settings."""

    settings = get_settings()
    console.print(
        {
            "app_env": settings.app_env,
            "log_level": settings.log_level,
            "scraper_max_requests_per_minute": settings.scraper_max_requests_per_minute,
            "scraper_min_delay_seconds": settings.scraper_min_delay_seconds,
            "scraper_timeout_seconds": settings.scraper_timeout_seconds,
            "scraper_cache_dir": str(settings.scraper_cache_dir),
            "scraper_force_refresh": settings.scraper_force_refresh,
        }
    )


@cache_app.command("path")
def cache_path(url: str) -> None:
    """Show the local cache path for a URL without downloading it."""

    settings = get_settings()
    cache = HtmlCache(settings.scraper_cache_dir)
    path: Path = cache.path_for_url(url)
    console.print(str(path))


@backfill_app.command("dry-run")
def backfill_dry_run(manifest_path: Path) -> None:
    """Validate and plan an approved manifest without downloading anything."""

    settings = get_settings()
    cache = HtmlCache(settings.scraper_cache_dir)
    try:
        report = dry_run_backfill_manifest(manifest_path, cache=cache)
    except ManifestValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc
    console.print_json(data=report.to_dict())
