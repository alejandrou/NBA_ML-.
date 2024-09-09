from peewee import Model, CharField, AutoField, ForeignKeyField, IntegerField
from db_manager.db_conf import db
from models.team.team import Team

class TeamRegularSeasonResults(Model):
    
    # ['g', 'date_game', 'game_start_time', 'network', 'box_score_text', 'game_location', 'opp_name', 'game_result', 
    # 'overtimes', 'pts', 'opp_pts', 'wins', 'losses', 'game_streak', 'attendance', 'game_duration', 'game_remarks']
    id_team_regular_season_results = AutoField(primary_key=True)
    id_team = ForeignKeyField(Team, to_field="id_team")
    game = IntegerField()
    date = CharField()
    hour_of_start = CharField()




    team_name = CharField(unique=True)
    team_abbreviation = CharField()
    league = CharField()
    from_year = CharField()
    to_year = CharField()
    years = CharField()
    games = CharField()
    wins = CharField()
    losses = CharField()
    win_loss_percentage = CharField()
    playoffs = CharField()
    division = CharField()
    conference = CharField()
    championships = CharField()
    
    class Meta:
        database = db
        schema = 'teams'
        table_name = 'team_regular_season_results'