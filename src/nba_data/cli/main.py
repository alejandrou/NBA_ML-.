import json
from pathlib import Path

import typer
from rich.console import Console

from nba_data import __version__
from nba_data.config.settings import get_settings
from nba_data.db.session import create_db_engine, create_session_factory
from nba_data.scraping.backfill_manifest import (
    BackfillAcquisitionError,
    ManifestValidationError,
    dry_run_backfill_manifest,
    run_backfill_acquisition,
)
from nba_data.scraping.cache import HtmlCache
from nba_data.scraping.client import BasketballReferenceClient
from nba_data.scraping.nba_team_season_acquisition import (
    NbaTeamSeasonAcquisitionConfigurationError,
    NbaTeamSeasonAcquisitionStopped,
    acquire_nba_team_season_manifest,
    build_verified_nba_team_season_acquisition_manifest,
    validate_phase_4d_acquisition_settings,
)
from nba_data.scraping.nba_team_season_manifest import build_nba_team_season_dry_run_report
from nba_data.scraping.offline_backfill import run_full_offline_backfill

app = typer.Typer(help="Safe local utilities for the NBA data platform.")
cache_app = typer.Typer(help="HTML cache utilities.")
backfill_app = typer.Typer(help="Controlled raw HTML backfill utilities.")
acquisition_app = typer.Typer(help="Phase 4D-A acquisition planning utilities.")
app.add_typer(cache_app, name="cache")
app.add_typer(backfill_app, name="backfill")
app.add_typer(acquisition_app, name="acquisition")
console = Console()
_ACQUISITION_OUTPUT_OPTION = typer.Option(
    None,
    "--output",
    help="Optional path to write the acquisition JSON report.",
)
_OFFLINE_BACKFILL_OUTPUT_OPTION = typer.Option(
    None,
    "--output",
    help="Optional path to write the offline backfill JSON report.",
)


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


@backfill_app.command("acquire")
def backfill_acquire(
    manifest_path: Path,
    execute_approved_manifest: bool = typer.Option(
        False,
        "--execute-approved-manifest",
        help="Required explicit confirmation for an approved manifest acquisition.",
    ),
) -> None:
    """Run a controlled cache-first acquisition for an approved manifest."""

    if not execute_approved_manifest:
        msg = "Refusing acquisition without --execute-approved-manifest"
        console.print(msg)
        raise typer.Exit(code=1)

    settings = get_settings()
    cache = HtmlCache(settings.scraper_cache_dir)
    try:
        with BasketballReferenceClient(settings) as client:
            report = run_backfill_acquisition(manifest_path, cache=cache, client=client)
    except ManifestValidationError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except BackfillAcquisitionError as exc:
        console.print_json(data=exc.report.to_dict())
        raise typer.Exit(code=1) from exc

    console.print_json(data=report.to_dict())


@backfill_app.command("offline")
def backfill_offline(
    execute_approved_backfill: bool = typer.Option(
        False,
        "--execute-approved-backfill",
        help="Required explicit confirmation to write PostgreSQL rows from cached HTML.",
    ),
    max_workers: int = typer.Option(
        1,
        "--max-workers",
        help="Local worker count for processing already-cached HTML files.",
    ),
    output: Path | None = _OFFLINE_BACKFILL_OUTPUT_OPTION,
) -> None:
    """Run Phase 4D full offline backfill from cached inventory entries."""

    if not execute_approved_backfill:
        msg = "Refusing offline backfill without --execute-approved-backfill"
        console.print(msg)
        raise typer.Exit(code=1)
    if max_workers < 1:
        raise typer.BadParameter("max_workers must be at least 1")

    settings = get_settings()
    cache = HtmlCache(settings.scraper_cache_dir)
    engine = create_db_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        with session_factory() as session, session.begin():
            report = run_full_offline_backfill(
                cache=cache,
                session=session,
                max_workers=max_workers,
            )
    finally:
        engine.dispose()

    _print_and_optionally_write_json(report.to_dict(), output)


@acquisition_app.command("dry-run-nba-team-seasons")
def acquisition_dry_run_nba_team_seasons() -> None:
    """Plan the Phase 4D-A NBA team-season manifest without downloading anything."""

    settings = get_settings()
    cache = HtmlCache(settings.scraper_cache_dir)
    report = build_nba_team_season_dry_run_report(cache=cache)
    console.print_json(data=report.to_dict())


@acquisition_app.command("acquire-nba-team-seasons")
def acquisition_acquire_nba_team_seasons(
    start_year: int,
    end_year: int,
    owner_approved: bool = typer.Option(
        False,
        "--owner-approved",
        help="Required explicit owner approval for the deterministic NBA team-season manifest.",
    ),
    execute_approved_manifest: bool = typer.Option(
        False,
        "--execute-approved-manifest",
        help="Required explicit confirmation to execute the approved acquisition.",
    ),
    output: Path | None = _ACQUISITION_OUTPUT_OPTION,
) -> None:
    """Run controlled Phase 4D-A NBA team-season cache acquisition."""

    if not owner_approved or not execute_approved_manifest:
        msg = "Refusing acquisition without --owner-approved and --execute-approved-manifest"
        console.print(msg)
        raise typer.Exit(code=1)

    settings = get_settings()
    try:
        validate_phase_4d_acquisition_settings(settings)
        manifest = build_verified_nba_team_season_acquisition_manifest(
            start_year=start_year,
            end_year=end_year,
        )
    except NbaTeamSeasonAcquisitionConfigurationError as exc:
        raise typer.BadParameter(str(exc)) from exc

    cache = HtmlCache(settings.scraper_cache_dir)
    try:
        with BasketballReferenceClient(settings, max_429_retries=0) as client:
            report = acquire_nba_team_season_manifest(manifest, cache=cache, client=client)
    except NbaTeamSeasonAcquisitionStopped as exc:
        _print_and_optionally_write_json(exc.report.to_dict(), output)
        raise typer.Exit(code=1) from exc

    _print_and_optionally_write_json(report.to_dict(), output)


def _print_and_optionally_write_json(data: dict[str, object], output: Path | None) -> None:
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    console.print_json(data=data)
