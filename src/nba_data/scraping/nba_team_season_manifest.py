from __future__ import annotations

import re
from dataclasses import dataclass

from nba_data.scraping.cache import HtmlCache

BASE_URL = "https://www.basketball-reference.com"
PAGE_TYPE = "team_season"
MANIFEST_ID = "nba-team-season-2000-2025"
SEASON_START_YEAR = 2000
SEASON_END_YEAR = 2025
EXPECTED_MANIFEST_URLS = 775

STABLE_TEAMS = (
    "ATL",
    "BOS",
    "CHI",
    "CLE",
    "DAL",
    "DEN",
    "DET",
    "GSW",
    "HOU",
    "IND",
    "LAC",
    "LAL",
    "MIA",
    "MIL",
    "MIN",
    "NYK",
    "ORL",
    "PHI",
    "PHO",
    "POR",
    "SAC",
    "SAS",
    "TOR",
    "UTA",
    "WAS",
)

_TEAM_SEASON_URL_RE = re.compile(
    r"^https://www\.basketball-reference\.com/teams/[A-Z]{3}/[0-9]{4}\.html$"
)


@dataclass(frozen=True)
class NbaTeamSeasonManifestEntry:
    page_type: str
    team: str
    season_end_year: int
    url: str

    def to_dict(self) -> dict[str, object]:
        return {
            "page_type": self.page_type,
            "team": self.team,
            "season_end_year": self.season_end_year,
            "url": self.url,
        }


@dataclass(frozen=True)
class NbaTeamSeasonManifest:
    manifest_id: str
    season_start_year: int
    season_end_year: int
    total_urls: int
    unique_urls: int
    entries: tuple[NbaTeamSeasonManifestEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "season_start_year": self.season_start_year,
            "season_end_year": self.season_end_year,
            "total_urls": self.total_urls,
            "unique_urls": self.unique_urls,
            "entries": [entry.to_dict() for entry in self.entries],
        }


@dataclass(frozen=True)
class NbaTeamSeasonDryRunEntry:
    page_type: str
    team: str
    season_end_year: int
    url: str
    cache_path: str
    cache_status: str
    estimated_fetch_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "page_type": self.page_type,
            "team": self.team,
            "season_end_year": self.season_end_year,
            "url": self.url,
            "cache_path": self.cache_path,
            "cache_status": self.cache_status,
            "estimated_fetch_count": self.estimated_fetch_count,
        }


@dataclass(frozen=True)
class NbaTeamSeasonDryRunReport:
    manifest_id: str
    season_start_year: int
    season_end_year: int
    total_urls: int
    unique_urls: int
    cache_hits: int
    missing_cache_entries: int
    skipped_entries: int
    unsupported_entries: int
    estimated_fetch_count: int
    entries: tuple[NbaTeamSeasonDryRunEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "manifest_id": self.manifest_id,
            "season_start_year": self.season_start_year,
            "season_end_year": self.season_end_year,
            "total_urls": self.total_urls,
            "unique_urls": self.unique_urls,
            "cache_hits": self.cache_hits,
            "missing_cache_entries": self.missing_cache_entries,
            "skipped_entries": self.skipped_entries,
            "unsupported_entries": self.unsupported_entries,
            "estimated_fetch_count": self.estimated_fetch_count,
            "entries": [entry.to_dict() for entry in self.entries],
        }


def build_nba_team_season_manifest() -> NbaTeamSeasonManifest:
    entries = tuple(
        NbaTeamSeasonManifestEntry(
            page_type=PAGE_TYPE,
            team=team,
            season_end_year=season_end_year,
            url=_build_team_season_url(team, season_end_year),
        )
        for season_end_year in range(SEASON_START_YEAR, SEASON_END_YEAR + 1)
        for team in _active_teams_for_season(season_end_year)
    )
    _validate_manifest_entries(entries)

    urls = {entry.url for entry in entries}
    return NbaTeamSeasonManifest(
        manifest_id=MANIFEST_ID,
        season_start_year=SEASON_START_YEAR,
        season_end_year=SEASON_END_YEAR,
        total_urls=len(entries),
        unique_urls=len(urls),
        entries=entries,
    )


def build_nba_team_season_dry_run_report(*, cache: HtmlCache) -> NbaTeamSeasonDryRunReport:
    manifest = build_nba_team_season_manifest()
    entries: list[NbaTeamSeasonDryRunEntry] = []
    cache_hits = 0
    missing_cache_entries = 0

    for manifest_entry in manifest.entries:
        cache_path = cache.path_for_url(manifest_entry.url)
        if cache_path.exists():
            cache_status = "hit"
            estimated_fetch_count = 0
            cache_hits += 1
        else:
            cache_status = "missing"
            estimated_fetch_count = 1
            missing_cache_entries += 1

        entries.append(
            NbaTeamSeasonDryRunEntry(
                page_type=manifest_entry.page_type,
                team=manifest_entry.team,
                season_end_year=manifest_entry.season_end_year,
                url=manifest_entry.url,
                cache_path=str(cache_path),
                cache_status=cache_status,
                estimated_fetch_count=estimated_fetch_count,
            )
        )

    return NbaTeamSeasonDryRunReport(
        manifest_id=manifest.manifest_id,
        season_start_year=manifest.season_start_year,
        season_end_year=manifest.season_end_year,
        total_urls=manifest.total_urls,
        unique_urls=manifest.unique_urls,
        cache_hits=cache_hits,
        missing_cache_entries=missing_cache_entries,
        skipped_entries=0,
        unsupported_entries=0,
        estimated_fetch_count=missing_cache_entries,
        entries=tuple(entries),
    )


def _active_teams_for_season(season_end_year: int) -> tuple[str, ...]:
    if season_end_year < SEASON_START_YEAR or season_end_year > SEASON_END_YEAR:
        msg = f"season_end_year must be between {SEASON_START_YEAR} and {SEASON_END_YEAR}"
        raise ValueError(msg)

    return (
        *STABLE_TEAMS,
        _grizzlies_team_for_season(season_end_year),
        _hornets_pelicans_team_for_season(season_end_year),
        *_bobcats_hornets_teams_for_season(season_end_year),
        _nets_team_for_season(season_end_year),
        _supersonics_thunder_team_for_season(season_end_year),
    )


def _grizzlies_team_for_season(season_end_year: int) -> str:
    if season_end_year <= 2001:
        return "VAN"
    return "MEM"


def _hornets_pelicans_team_for_season(season_end_year: int) -> str:
    if season_end_year <= 2002:
        return "CHH"
    if season_end_year <= 2005 or 2008 <= season_end_year <= 2013:
        return "NOH"
    if season_end_year <= 2007:
        return "NOK"
    return "NOP"


def _bobcats_hornets_teams_for_season(season_end_year: int) -> tuple[str, ...]:
    if season_end_year <= 2004:
        return ()
    if season_end_year <= 2014:
        return ("CHA",)
    return ("CHO",)


def _nets_team_for_season(season_end_year: int) -> str:
    if season_end_year <= 2012:
        return "NJN"
    return "BRK"


def _supersonics_thunder_team_for_season(season_end_year: int) -> str:
    if season_end_year <= 2008:
        return "SEA"
    return "OKC"


def _build_team_season_url(team: str, season_end_year: int) -> str:
    return f"{BASE_URL}/teams/{team}/{season_end_year}.html"


def _validate_manifest_entries(entries: tuple[NbaTeamSeasonManifestEntry, ...]) -> None:
    urls = [entry.url for entry in entries]
    unique_urls = set(urls)
    if len(entries) != EXPECTED_MANIFEST_URLS or len(unique_urls) != EXPECTED_MANIFEST_URLS:
        msg = (
            "NBA team-season manifest must contain exactly "
            f"{EXPECTED_MANIFEST_URLS} unique URLs"
        )
        raise ValueError(msg)

    for entry in entries:
        if entry.page_type != PAGE_TYPE:
            msg = "NBA team-season manifest entries must use page_type='team_season'"
            raise ValueError(msg)
        if not _TEAM_SEASON_URL_RE.fullmatch(entry.url):
            msg = f"Unsupported NBA team-season URL: {entry.url}"
            raise ValueError(msg)
