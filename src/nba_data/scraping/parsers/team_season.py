from __future__ import annotations

from types import MappingProxyType

from bs4 import BeautifulSoup, Comment, Tag

SUPPORTED_TEAM_SEASON_TABLES = MappingProxyType(
    {
        "roster": "roster",
        "totals": "totals_stats",
        "per_game": "per_game_stats",
        "per_minute": "per_minute_stats",
        "per_poss": "per_poss",
        "advanced": "advanced",
        "shooting": "shooting",
        "adj_shooting": "adj_shooting",
        "pbp": "pbp_stats",
    }
)


def parse_team_season_page(html: str) -> dict[str, list[dict[str, str]]]:
    """Parse supported tables from one Basketball Reference team-season page."""

    soup = _soup_with_commented_tables(html)
    return {
        source_table: _parse_table(soup, table_id)
        for source_table, table_id in SUPPORTED_TEAM_SEASON_TABLES.items()
    }


def parse_roster(html: str) -> list[dict[str, str]]:
    return parse_team_season_page(html)["roster"]


def _soup_with_commented_tables(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "lxml")
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        if "<table" not in comment:
            continue
        comment_soup = BeautifulSoup(str(comment), "lxml")
        body = comment_soup.body
        if body is None:
            continue
        for child in list(body.children):
            if isinstance(child, Tag):
                soup.append(child)
    return soup


def _parse_table(soup: BeautifulSoup, table_id: str) -> list[dict[str, str]]:
    table = soup.find("table", id=table_id)
    if table is None:
        return []

    headers = _headers(table)
    rows: list[dict[str, str]] = []
    tbody = table.find("tbody")
    if tbody is None:
        return rows

    for tr in tbody.find_all("tr", recursive=False):
        cells = tr.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        if _is_repeated_header_row(tr, cells):
            continue
        row = {}
        for index, cell in enumerate(cells):
            if index >= len(headers):
                break
            header = headers[index]
            row[header] = cell.get_text(strip=True)
            player_id = _basketball_reference_player_id(cell)
            if player_id is not None:
                row["basketball_reference_player_id"] = player_id
        if row:
            rows.append(row)
    return rows


def _is_repeated_header_row(tr: Tag, cells: list[Tag]) -> bool:
    if "thead" in tr.get("class", []):
        return True

    data_stats = [cell.get("data-stat") for cell in cells]
    cell_text = [cell.get_text(strip=True).lower() for cell in cells]
    return data_stats == cell_text


def _headers(table: Tag) -> list[str]:
    thead = table.find("thead")
    if thead is None:
        return []
    header_row = thead.find_all("tr")[-1]
    headers = []
    for cell in header_row.find_all(["th", "td"], recursive=False):
        data_stat = cell.get("data-stat")
        label = data_stat if data_stat else cell.get_text(strip=True)
        headers.append(label)
    return headers


def _basketball_reference_player_id(cell: Tag) -> str | None:
    link = cell.find("a", href=True)
    if link is None:
        return None

    href = str(link["href"])
    prefix = "/players/"
    suffix = ".html"
    if not href.startswith(prefix) or not href.endswith(suffix):
        return None

    player_file = href.rsplit("/", maxsplit=1)[-1]
    return player_file.removesuffix(suffix) or None
