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
from nba_data.scraping.offline_player_stats_backfill import (
    DEFAULT_PLAYER_STATS_PARSER_VERSION,
    run_offline_player_stats_backfill,
)
from nba_data.scraping.offline_stats_backfill import (
    DEFAULT_STATS_PARSER_VERSION,
    run_offline_stats_backfill,
)
from nba_data.validation.official_stats import (
    validate_official_stats as run_official_stats_validation,
)
from nba_data.validation.offline_database import (
    validate_offline_database as run_offline_database_validation,
)

app = typer.Typer(help="Safe local utilities for the NBA data platform.")
cache_app = typer.Typer(help="HTML cache utilities.")
backfill_app = typer.Typer(help="Controlled raw HTML backfill utilities.")
acquisition_app = typer.Typer(help="Phase 4D-A acquisition planning utilities.")
validation_app = typer.Typer(help="Offline data quality validation utilities.")
app.add_typer(cache_app, name="cache")
app.add_typer(backfill_app, name="backfill")
app.add_typer(acquisition_app, name="acquisition")
app.add_typer(validation_app, name="validate")
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
_STATS_BACKFILL_OUTPUT_OPTION = typer.Option(
    None,
    "--output",
    help="Optional path to write the offline stats backfill JSON report.",
)
_OFFLINE_DATABASE_BACKFILL_REPORT_OPTION = typer.Option(
    ...,
    "--backfill-report",
    exists=True,
    dir_okay=False,
    readable=True,
    help="Path to the Phase 4D offline backfill JSON report.",
)
_OFFICIAL_STATS_BACKFILL_REPORT_OPTION = typer.Option(
    None,
    "--stats-backfill-report",
    exists=True,
    dir_okay=False,
    readable=True,
    help="Optional path to the Phase 4E stats backfill JSON report.",
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


@backfill_app.command("stats")
def backfill_stats(
    execute_approved_stats_backfill: bool = typer.Option(
        False,
        "--execute-approved-stats-backfill",
        help="Required explicit confirmation to write stats rows from cached HTML.",
    ),
    max_workers: int = typer.Option(
        1,
        "--max-workers",
        help="Local worker count for processing already-cached HTML files.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Optional positive limit for smoke-test sized offline stats backfills.",
    ),
    team: str | None = typer.Option(
        None,
        "--team",
        help="Optional real team abbreviation filter.",
    ),
    start_year: int | None = typer.Option(
        None,
        "--start-year",
        help="Optional first season end year to include.",
    ),
    end_year: int | None = typer.Option(
        None,
        "--end-year",
        help="Optional last season end year to include.",
    ),
    parser_version: str = typer.Option(
        DEFAULT_STATS_PARSER_VERSION,
        "--parser-version",
        help="Parser/normalizer contract label to store in stats lineage.",
    ),
    output: Path | None = _STATS_BACKFILL_OUTPUT_OPTION,
) -> None:
    """Run Phase 4E offline stats backfill from cached inventory entries."""

    if not execute_approved_stats_backfill:
        msg = "Refusing stats backfill without --execute-approved-stats-backfill"
        console.print(msg)
        raise typer.Exit(code=1)

    settings = get_settings()
    cache = HtmlCache(settings.scraper_cache_dir)
    engine = create_db_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        with session_factory() as session, session.begin():
            try:
                report = run_offline_stats_backfill(
                    session,
                    cache=cache,
                    max_workers=max_workers,
                    limit=limit,
                    team=team,
                    start_year=start_year,
                    end_year=end_year,
                    parser_version=parser_version,
                )
            except ValueError as exc:
                raise typer.BadParameter(str(exc)) from exc
    finally:
        engine.dispose()

    _print_and_optionally_write_json(report.to_dict(), output)


@backfill_app.command("player-stats")
def backfill_player_stats(
    execute_approved_player_stats_backfill: bool = typer.Option(
        False,
        "--execute-approved-player-stats-backfill",
        help="Required explicit confirmation to write player-page stats rows from cached HTML.",
    ),
    limit: int | None = typer.Option(
        None,
        "--limit",
        help="Optional positive limit for smoke-test sized player-page stats backfills.",
    ),
    player: str | None = typer.Option(
        None,
        "--player",
        help="Optional basketball_reference_player_id filter.",
    ),
    start_year: int | None = typer.Option(
        None,
        "--start-year",
        help="Optional first season end year to include.",
    ),
    end_year: int | None = typer.Option(
        None,
        "--end-year",
        help="Optional last season end year to include.",
    ),
    parser_version: str = typer.Option(
        DEFAULT_PLAYER_STATS_PARSER_VERSION,
        "--parser-version",
        help="Parser/normalizer contract label to store in stats lineage.",
    ),
    output: Path | None = _STATS_BACKFILL_OUTPUT_OPTION,
) -> None:
    """Run cache-only player-page regular-season aggregate stats backfill."""

    if not execute_approved_player_stats_backfill:
        msg = (
            "Refusing player-page stats backfill without "
            "--execute-approved-player-stats-backfill"
        )
        console.print(msg)
        raise typer.Exit(code=1)

    settings = get_settings()
    cache = HtmlCache(settings.scraper_cache_dir)
    engine = create_db_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        with session_factory() as session, session.begin():
            try:
                report = run_offline_player_stats_backfill(
                    session,
                    cache=cache,
                    limit=limit,
                    player=player,
                    start_year=start_year,
                    end_year=end_year,
                    parser_version=parser_version,
                )
            except ValueError as exc:
                raise typer.BadParameter(str(exc)) from exc
    finally:
        engine.dispose()

    _print_and_optionally_write_json(report.to_dict(), output)


@validation_app.command("offline-database")
def validate_offline_database(
    backfill_report: Path = _OFFLINE_DATABASE_BACKFILL_REPORT_OPTION,
) -> None:
    """Validate the local Phase 4D PostgreSQL core database state."""

    try:
        backfill_data = json.loads(backfill_report.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid backfill report JSON: {exc}") from exc

    settings = get_settings()
    engine = create_db_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        with session_factory() as session:
            report = run_offline_database_validation(session, backfill_data)
    finally:
        engine.dispose()

    console.print_json(data=report.to_dict())
    if not report.passed:
        raise typer.Exit(code=1)


@validation_app.command("official-stats")
def validate_official_stats(
    stats_backfill_report: Path | None = _OFFICIAL_STATS_BACKFILL_REPORT_OPTION,
) -> None:
    """Validate the local Phase 4E official stats state."""

    backfill_data: dict[str, object] | None = None
    if stats_backfill_report is not None:
        try:
            loaded = json.loads(stats_backfill_report.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise typer.BadParameter(f"Invalid stats backfill report JSON: {exc}") from exc
        if not isinstance(loaded, dict):
            raise typer.BadParameter("Stats backfill report JSON must be an object.")
        backfill_data = loaded

    settings = get_settings()
    engine = create_db_engine(settings)
    try:
        session_factory = create_session_factory(engine)
        with session_factory() as session:
            report = run_official_stats_validation(session, backfill_data)
    finally:
        engine.dispose()

    console.print_json(data=report.to_dict())
    if not report.passed:
        raise typer.Exit(code=1)


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
