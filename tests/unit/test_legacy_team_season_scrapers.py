from pathlib import Path

import pytest
from db_manager.player_operations.player_operations import PlayerOperations
from scrap.scrap_player.scrap_player_advanced import PlayerScraperAdvanced
from scrap.scrap_player.scrap_player_roster import PlayerScraperRoster
from scrap.scrap_player.scrap_player_totals import PlayerScraperTotals

FIXTURE = Path("tests/fixtures/html/team_season_realistic.html")


class FakeTeamSeasonHtmlProvider:
    def __init__(self, html: str) -> None:
        self.html = html
        self.calls: list[tuple[str, int]] = []

    def get_html(self, team_abbreviation: str, year: int) -> str:
        self.calls.append((team_abbreviation, year))
        return self.html


@pytest.mark.unit
@pytest.mark.asyncio
async def test_legacy_roster_scraper_can_read_provider_html_without_http_client() -> None:
    provider = FakeTeamSeasonHtmlProvider(FIXTURE.read_text(encoding="utf-8"))
    scraper = PlayerScraperRoster([2024], team_season_html_provider=provider)

    rows = await scraper.scrape_team_year_roster("BOS", 2024)

    assert provider.calls == [("BOS", 2024)]
    assert rows[0]["Player"] == "Jayson Tatum"
    assert rows[0]["Pos"] == "SF"
    assert rows[0]["Ht"] == "6-8"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_legacy_totals_scraper_preserves_loader_compatible_keys() -> None:
    provider = FakeTeamSeasonHtmlProvider(FIXTURE.read_text(encoding="utf-8"))
    scraper = PlayerScraperTotals([2024], team_season_html_provider=provider)

    rows = await scraper.scrape_team_year_totals("BOS", 2024)

    assert provider.calls == [("BOS", 2024)]
    assert rows[0]["Player"] == "Jayson Tatum"
    assert rows[0]["G"] == "74"
    assert rows[0]["PTS"] == "1987"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_legacy_advanced_scraper_preserves_loader_compatible_keys() -> None:
    provider = FakeTeamSeasonHtmlProvider(FIXTURE.read_text(encoding="utf-8"))
    scraper = PlayerScraperAdvanced([2024], team_season_html_provider=provider)

    rows = await scraper.scrape_team_year_advanced("BOS", 2024)

    assert provider.calls == [("BOS", 2024)]
    assert rows[0]["Player"] == "Jayson Tatum"
    assert rows[0]["PER"] == "22.3"
    assert rows[0]["TS%"] == ".604"


@pytest.mark.unit
def test_player_operations_wires_shared_adapter_into_legacy_scrapers() -> None:
    provider = FakeTeamSeasonHtmlProvider(FIXTURE.read_text(encoding="utf-8"))

    operations = PlayerOperations([2024], team_season_html_provider=provider)

    assert operations.scraper_roster.team_season_html_provider is provider
    assert operations.scraper_totals.team_season_html_provider is provider
    assert operations.scraper_advanced.team_season_html_provider is provider
    assert operations.scraper_roster.team_season_table_adapter is operations.team_season_table_adapter
    assert operations.scraper_totals.team_season_table_adapter is operations.team_season_table_adapter
    assert operations.scraper_advanced.team_season_table_adapter is operations.team_season_table_adapter


@pytest.mark.unit
@pytest.mark.asyncio
async def test_player_operations_reuses_one_html_read_for_roster_totals_and_advanced() -> None:
    provider = FakeTeamSeasonHtmlProvider(FIXTURE.read_text(encoding="utf-8"))
    operations = PlayerOperations([2024], team_season_html_provider=provider)

    roster = await operations.scraper_roster.scrape_team_year_roster("BOS", 2024)
    totals = await operations.scraper_totals.scrape_team_year_totals("BOS", 2024)
    advanced = await operations.scraper_advanced.scrape_team_year_advanced("BOS", 2024)

    assert provider.calls == [("BOS", 2024)]
    assert roster[0]["Player"] == "Jayson Tatum"
    assert totals[0]["PTS"] == "1987"
    assert advanced[0]["PER"] == "22.3"


@pytest.mark.unit
def test_consolidated_player_scrapers_do_not_keep_direct_live_http_paths() -> None:
    paths = [
        Path("scrap/scrap_player/scrap_player_roster.py"),
        Path("scrap/scrap_player/scrap_player_totals.py"),
        Path("scrap/scrap_player/scrap_player_advanced.py"),
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert "httpx" not in source
    assert "AsyncClient" not in source
    assert "client.get" not in source
    assert "asyncio.sleep" not in source
    assert "asyncio.gather" not in source
