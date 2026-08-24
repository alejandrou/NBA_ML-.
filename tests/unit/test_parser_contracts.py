from __future__ import annotations

import pytest

from nba_data.scraping.offline_player_postseason_stats_backfill import (
    DEFAULT_PLAYER_POSTSEASON_STATS_PARSER_VERSION,
)
from nba_data.scraping.offline_player_stats_backfill import (
    DEFAULT_PLAYER_STATS_PARSER_VERSION,
)
from nba_data.scraping.offline_stats_backfill import DEFAULT_STATS_PARSER_VERSION
from nba_data.validation.official_stats import STATS_TABLE_SPECS
from nba_data.validation.parser_contracts import (
    CURRENT_PARSER_CONTRACTS,
    PARSER_CONTRACTS,
    PARSER_CONTRACTS_BY_IDENTIFIER,
    PARSER_PRODUCERS,
    classify_parser_version,
    current_parser_version,
)


@pytest.mark.unit
def test_registry_has_no_duplicate_identifiers() -> None:
    identifiers = [contract.identifier for contract in PARSER_CONTRACTS]
    assert len(identifiers) == len(set(identifiers))
    assert len(PARSER_CONTRACTS_BY_IDENTIFIER) == len(PARSER_CONTRACTS)


@pytest.mark.unit
def test_every_producer_has_exactly_one_current_contract() -> None:
    for producer in PARSER_PRODUCERS:
        current = [
            contract
            for contract in PARSER_CONTRACTS
            if contract.producer == producer and contract.is_current
        ]
        assert len(current) == 1, f"{producer} must have exactly one current contract"
    assert set(CURRENT_PARSER_CONTRACTS) == set(PARSER_PRODUCERS)


@pytest.mark.unit
def test_regular_and_postseason_current_entries_share_generation_but_not_identifier() -> None:
    regular = CURRENT_PARSER_CONTRACTS["player_page_regular"]
    postseason = CURRENT_PARSER_CONTRACTS["player_page_postseason"]

    assert regular.generation == postseason.generation
    assert regular.identifier != postseason.identifier


@pytest.mark.unit
@pytest.mark.parametrize(
    "producer,expected_default",
    [
        ("team_season", DEFAULT_STATS_PARSER_VERSION),
        ("player_page_regular", DEFAULT_PLAYER_STATS_PARSER_VERSION),
        ("player_page_postseason", DEFAULT_PLAYER_POSTSEASON_STATS_PARSER_VERSION),
    ],
)
def test_backfill_default_matches_registry_current_entry(
    producer: str, expected_default: str
) -> None:
    assert current_parser_version(producer) == expected_default  # type: ignore[arg-type]


@pytest.mark.unit
def test_every_registered_identifier_classifies_as_current_or_stale() -> None:
    for contract in PARSER_CONTRACTS:
        expected = "current" if contract.is_current else "stale"
        assert classify_parser_version(contract.identifier) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "value",
    ["", "   ", "not-a-real-parser", "player-page-parser-v99", None, 42],
)
def test_unregistered_or_blank_values_classify_as_unknown(value: object) -> None:
    assert classify_parser_version(value) == "unknown"


@pytest.mark.unit
def test_registry_represents_every_historical_player_page_version() -> None:
    player_page_identifiers = {
        contract.identifier
        for contract in PARSER_CONTRACTS
        if contract.producer in ("player_page_regular", "player_page_postseason")
    }
    for version in range(1, 5):
        assert f"player-page-parser-v{version}" in player_page_identifiers
        assert f"player-page-postseason-parser-v{version}" in player_page_identifiers


@pytest.mark.unit
def test_team_season_registry_has_one_current_entry() -> None:
    assert "team-season-parser-v1" in PARSER_CONTRACTS_BY_IDENTIFIER
    assert PARSER_CONTRACTS_BY_IDENTIFIER["team-season-parser-v1"].is_current is True


@pytest.mark.unit
def test_expected_parser_producer_matches_table_season_type_and_family() -> None:
    for spec in STATS_TABLE_SPECS:
        if spec.season_type == "postseason":
            assert spec.expected_parser_producer == "player_page_postseason"
        elif spec.family == "aggregate":
            assert spec.expected_parser_producer == "player_page_regular"
        else:
            assert spec.expected_parser_producer == "team_season"


@pytest.mark.unit
def test_every_table_expected_producer_is_a_real_producer() -> None:
    for spec in STATS_TABLE_SPECS:
        assert spec.expected_parser_producer in PARSER_PRODUCERS
