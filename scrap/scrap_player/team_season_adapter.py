from nba_data.scraping.parsers.team_season import parse_team_season_page


LEGACY_KEY_MAP = {
    "roster": {
        "number": "No.",
        "player": "Player",
        "pos": "Pos",
        "height": "Ht",
        "weight": "Wt",
        "birth_date": "Birth Date",
        "years_experience": "Exp",
        "experience": "Exp",
        "college": "College",
    },
    "totals": {
        "rk": "Rk",
        "player": "Player",
        "age": "Age",
        "g": "G",
        "gs": "GS",
        "mp": "MP",
        "fg": "FG",
        "fga": "FGA",
        "fg_pct": "FG%",
        "fg3": "3P",
        "fg3a": "3PA",
        "fg3_pct": "3P%",
        "fg2": "2P",
        "fg2a": "2PA",
        "fg2_pct": "2P%",
        "efg_pct": "eFG%",
        "ft": "FT",
        "fta": "FTA",
        "ft_pct": "FT%",
        "orb": "ORB",
        "drb": "DRB",
        "trb": "TRB",
        "ast": "AST",
        "stl": "STL",
        "blk": "BLK",
        "tov": "TOV",
        "pf": "PF",
        "pts": "PTS",
        "trp_dbl": "Trp-Dbl",
        "awards": "Awards",
    },
    "advanced": {
        "rk": "Rk",
        "player": "Player",
        "age": "Age",
        "g": "G",
        "mp": "MP",
        "per": "PER",
        "ts_pct": "TS%",
        "fg3a_per_fga_pct": "3PAr",
        "fta_per_fga_pct": "FTr",
        "orb_pct": "ORB%",
        "drb_pct": "DRB%",
        "trb_pct": "TRB%",
        "ast_pct": "AST%",
        "stl_pct": "STL%",
        "blk_pct": "BLK%",
        "tov_pct": "TOV%",
        "usg_pct": "USG%",
        "ows": "OWS",
        "dws": "DWS",
        "ws": "WS",
        "ws_per_48": "WS/48",
        "obpm": "OBPM",
        "dbpm": "DBPM",
        "bpm": "BPM",
        "vorp": "VORP",
        "awards": "Awards",
    },
}


class LegacyTeamSeasonTableAdapter:
    def __init__(self, team_season_html_provider):
        if team_season_html_provider is None:
            raise ValueError("team_season_html_provider is required")
        self.team_season_html_provider = team_season_html_provider
        self._parsed_cache = {}

    def get_roster(self, team_abbreviation, year):
        return self.get_table("roster", team_abbreviation, year)

    def get_totals(self, team_abbreviation, year):
        return self.get_table("totals", team_abbreviation, year)

    def get_advanced(self, team_abbreviation, year):
        return self.get_table("advanced", team_abbreviation, year)

    def get_table(self, table_name, team_abbreviation, year):
        parsed = self._parsed(team_abbreviation, year)
        rows = parsed.get(table_name, [])
        return [_legacy_row(table_name, row) for row in rows]

    def _parsed(self, team_abbreviation, year):
        cache_key = (team_abbreviation.strip().upper(), int(year))
        if cache_key not in self._parsed_cache:
            html = self.team_season_html_provider.get_html(*cache_key)
            self._parsed_cache[cache_key] = parse_team_season_page(html)
        return self._parsed_cache[cache_key]


def _legacy_row(table_name, row):
    key_map = LEGACY_KEY_MAP.get(table_name, {})
    return {key_map.get(key, key): value for key, value in row.items()}
