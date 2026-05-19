from __future__ import annotations

from bs4 import BeautifulSoup, Comment, Tag


def parse_team_season_page(html: str) -> dict[str, list[dict[str, str]]]:
    """Parse supported tables from one Basketball Reference team-season page."""

    soup = _soup_with_commented_tables(html)
    return {
        "roster": _parse_table(soup, "roster"),
        "totals": _parse_table(soup, "totals_stats"),
        "advanced": _parse_table(soup, "advanced"),
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
        if "thead" in tr.get("class", []):
            continue
        cells = tr.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        row = {}
        for index, cell in enumerate(cells):
            if index >= len(headers):
                break
            row[headers[index]] = cell.get_text(strip=True)
        if row:
            rows.append(row)
    return rows


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
