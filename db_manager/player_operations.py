from scrap.scrap_player.scrap_player_roster import PlayerScraperRoster
from scrap.scrap_player.scrap_player_totals import PlayerScraperTotals
from scrap.scrap_player.scrap_player_advanced import PlayerScraperAdvanced
from models.player.player import Player
from models.player.player_stats import PlayerStats
from models.player.player_advanced import PlayerAdvancedStats
from db_manager.db_manager import DBManager
from models.team.team import Team


class PlayerOperations:

    def __init__(self):
        self.scraper_roster = PlayerScraperRoster()
        self.scraper_totals = PlayerScraperTotals()
        self.scraper_advanced = PlayerScraperAdvanced()

    async def scrape_and_save_players_roster_async(self, client):
        DBManager.create_tables(Player)
        player_roster = await self.scraper_roster.get_players_team_year_roster(client)

        for team_name, years_data in player_roster.items():
            team_instance = Team.get(Team.team_abbreviation == team_name)
            batch_data = []  # Collect player data for batch insertion

            for year, players_data in years_data.items():
                for player in players_data:
                    player_data = {
                        'number_player': player.get('No.', None),
                        'id_team': team_instance.id_team,
                        'player_name': player.get('Player', None),
                        'player_position': player.get('Pos', None),
                        'player_height': player.get('Ht', None),
                        'player_weight': player.get('Wt', None),
                        'player_birth_date': player.get('Birth Date', None),
                        'player_experience': player.get('Exp', None),
                        'player_college': player.get('College', None),
                        'player_team': team_name,
                        'player_year_in_team': year,
                    }
                    batch_data.append(player_data)

            # Batch insert

            if batch_data:
                Player.insert_many(batch_data).execute()

    async def scrape_and_save_players_totals_async(self, client):
        DBManager.create_tables(PlayerStats)
        player_totals = await self.scraper_totals.get_players_team_year_totals(client)

        for nba_team, years_data in player_totals.items():
            for year, players_data in years_data.items():
                batch_data = []
                for player in players_data:
                    try:
                        player_instance = Player.get(
                            Player.player_name == player['Player'])
                    except Player.DoesNotExist:
                        print(
                            f"Player {player['Player']} not found for {nba_team} in {year}. Skipping...")
                        continue
                    player_data = {
                        'id_player': player_instance.id_player,
                        'player': player.get('Player', None),
                        'games': player.get('G', None),
                        'games_started': player.get('GS', None),
                        'minutes_played': player.get('MP', None),
                        'field_goals': player.get('FG', None),
                        'field_goals_attempted': player.get('FGA', None),
                        'field_goals_percentage': player.get('FG%', None),
                        'three_point_field_goals': player.get('3P', None),
                        'three_point_field_goals_attempted': player.get('3PA', None),
                        'three_point_field_goals_percentage': player.get('3P%', None),
                        'two_point_field_goals': player.get('2P', None),
                        'two_point_field_goals_attempted': player.get('2PA', None),
                        'two_point_field_goals_percentage': player.get('2P%', None),
                        'effective_field_goals_percentage': player.get('eFG%', None),
                        'free_throws': player.get('FT', None),
                        'free_throws_attempted': player.get('FTA', None),
                        'free_throws_percentage': player.get('FT%', None),
                        'offensive_rebounds': player.get('ORB', None),
                        'defensive_rebounds': player.get('DRB', None),
                        'total_rebounds': player.get('TRB', None),
                        'assists': player.get('AST', None),
                        'steals': player.get('STL', None),
                        'blocks': player.get('BLK', None),
                        'turnovers': player.get('TOV', None),
                        'personal_fouls': player.get('PF', None),
                        'points': player.get('PTS', None),
                        'triple_doubles': player.get('Trp-Dbl', None),
                        'awards': player.get('Awards', None),
                    }
                    batch_data.append(player_data)

                # Batch insert

                if batch_data:
                    PlayerStats.insert_many(batch_data).execute()

    async def scrape_and_save_players_advanced(self, client):
        DBManager.create_tables(PlayerAdvancedStats)
        player_advanced = await self.scraper_advanced.get_players_team_year_advanced(client)

        for nba_team, years_data in player_advanced.items():
            for year, players_data in years_data.items():
                batch_data = []
                for player in players_data:
                    try:
                        player_instance = Player.get(
                            Player.player_name == player['Player'])
                    except Player.DoesNotExist:
                        print(
                            f"Player {player['Player']} not found for {nba_team} in {year}. Skipping...")
                        continue
                    # Si se encuentra el jugador, crea el registro en PlayerAdvancedStats
                    player_data = {
                        'id_player': player_instance.id_player,  # Clave foránea de Player
                        'rk': player.get('Rk', None),
                        'player': player.get('Player', None),
                        'games': player.get('G', None),
                        'minutes_played': player.get('MP', None),
                        'player_effiencey_rating': player.get('PER', None),
                        'true_shooting_percentage': player.get('TS%', None),
                        'three_point_attempt_rate': player.get('3PAr', None),
                        'free_throw_attempt_rate': player.get('FTr', None),
                        'offensive_rebound_percentage': player.get('ORB%', None),
                        'defensive_rebound_percentage': player.get('DRB%', None),
                        'total_rebound_percentage': player.get('TRB%', None),
                        'assist_percentage': player.get('AST%', None),
                        'steal_percentage': player.get('STL%', None),
                        'block_percentage': player.get('BLK%', None),
                        'turnover_percentage': player.get('TOV%', None),
                        'usage_percentage': player.get('USG%', None),
                        'offensive_win_shares': player.get('OWS', None),
                        'defensive_win_shares': player.get('DWS', None),
                        'win_shares': player.get('WS', None),
                        'win_shares_per_48_minutes': player.get('WS/48', None),
                        'offensive_box_plus_minus': player.get('OBPM', None),
                        'defensive_box_plus_minus': player.get('DBPM', None),
                        'box_plus_minus': player.get('BPM', None),
                        'value_over_replacement_player': player.get('VORP', None),
                    }
                    batch_data.append(player_data)
                # Batch insert
            if batch_data:
                PlayerAdvancedStats.insert_many(batch_data).execute()
