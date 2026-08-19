from __future__ import annotations

from types import MappingProxyType

from bs4 import BeautifulSoup, Comment, Tag

from nba_data.validation.team_season import DataQualityIssue

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

TEAM_NAME_SELECTOR = "h1 > span:nth-of-type(2)"
TEAM_NAME_SOURCE_TABLE = "team_name"
TEAM_NAME_H1_MISSING = "team_name_h1_missing"
TEAM_NAME_H1_SPAN_COUNT = "team_name_h1_span_count"
TEAM_NAME_H1_SECOND_SPAN_EMPTY = "team_name_h1_second_span_empty"


class ParsedTeamSeasonPage(dict[str, list[dict[str, str]]]):
    """Parsed team-season tables plus the page-level team-name metadata."""

    def __init__(
        self,
        tables: dict[str, list[dict[str, str]]],
        *,
        team_name: str | None,
        team_name_issues: tuple[DataQualityIssue, ...] = (),
    ) -> None:
        super().__init__(tables)
        self.team_name = team_name
        self.team_name_issues = team_name_issues

    @property
    def issues(self) -> tuple[DataQualityIssue, ...]:
        """Expose page-level issues under the generic result name too."""

        return self.team_name_issues


def parse_team_season_page(html: str) -> ParsedTeamSeasonPage:
    """Parse supported tables from one Basketball Reference team-season page."""

    soup = _soup_with_commented_tables(html)
    tables = {
        source_table: _parse_table(soup, table_id)
        for source_table, table_id in SUPPORTED_TEAM_SEASON_TABLES.items()
    }
    team_name, team_name_issues = _parse_team_name(soup)
    return ParsedTeamSeasonPage(
        tables,
        team_name=team_name,
        team_name_issues=team_name_issues,
    )


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


def _parse_team_name(
    soup: BeautifulSoup,
) -> tuple[str | None, tuple[DataQualityIssue, ...]]:
    h1 = soup.find("h1")
    if h1 is None:
        return None, (_team_name_issue(TEAM_NAME_H1_MISSING, "no <h1> was found"),)

    spans = h1.find_all("span", recursive=False)
    if len(spans) != 3:
        return None, (
            _team_name_issue(
                TEAM_NAME_H1_SPAN_COUNT,
                f"expected exactly three direct <span> elements under <h1>, found {len(spans)}",
            ),
        )

    team_name = spans[1].get_text(" ", strip=True)
    if not team_name:
        return None, (
            _team_name_issue(
                TEAM_NAME_H1_SECOND_SPAN_EMPTY,
                f"the selector {TEAM_NAME_SELECTOR!r} resolved to an empty span",
            ),
        )

    return team_name, ()


def _team_name_issue(code: str, detail: str) -> DataQualityIssue:
    return DataQualityIssue(
        code=code,
        message=(
            f"Team-name selector contract {TEAM_NAME_SELECTOR!r} failed: {detail}; "
            "the team name is unset."
        ),
        source_table=TEAM_NAME_SOURCE_TABLE,
    )


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
