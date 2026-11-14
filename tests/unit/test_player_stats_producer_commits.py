"""The player-page producers commit page by page when asked (DATABASE_AUDIT_2026-11-10, R-03)."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

import nba_data.scraping.offline_player_postseason_stats_backfill as postseason
import nba_data.scraping.offline_player_stats_backfill as regular
from nba_data.scraping.cache import HtmlCache

PRODUCERS = (
    (regular, regular.run_offline_player_stats_backfill),
    (postseason, postseason.run_offline_player_postseason_stats_backfill),
)


class _Session:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def commit(self) -> None:
        self.events.append("commit")


def _three_pages(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch, events: list[str], tmp_path: Path
) -> None:
    pages = [(tmp_path / f"p{index}.html.gz", f"player0{index}", f"url{index}") for index in range(3)]
    monkeypatch.setattr(module, "resolve_player_cache_root", lambda root: root)
    monkeypatch.setattr(module, "discover_player_cache_entries", lambda root, **kwargs: pages)
    monkeypatch.setattr(module, "load_season_scope", lambda session: frozenset({2024}))

    def process(session: object, *, player_identifier: str, **kwargs: object) -> object:
        if player_identifier == "player02":
            raise KeyboardInterrupt
        events.append(f"load {player_identifier}")
        return SimpleNamespace()

    monkeypatch.setattr(module, "_process_one_player_page", process)


@pytest.mark.unit
@pytest.mark.parametrize(("module", "run"), PRODUCERS, ids=["regular", "postseason"])
def test_pages_before_an_interruption_stay_committed(
    module: ModuleType, run: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []
    _three_pages(module, monkeypatch, events, tmp_path)

    with pytest.raises(KeyboardInterrupt):
        run(_Session(events), cache=HtmlCache(tmp_path), commit_each_page=True)  # type: ignore[operator]

    assert events == ["load player00", "commit", "load player01", "commit"]


@pytest.mark.unit
@pytest.mark.parametrize(("module", "run"), PRODUCERS, ids=["regular", "postseason"])
def test_without_the_flag_nothing_is_committed(
    module: ModuleType, run: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    events: list[str] = []
    _three_pages(module, monkeypatch, events, tmp_path)

    with pytest.raises(KeyboardInterrupt):
        run(_Session(events), cache=HtmlCache(tmp_path))  # type: ignore[operator]

    assert "commit" not in events
