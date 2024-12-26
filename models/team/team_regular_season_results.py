from peewee import Model, CharField, AutoField, ForeignKeyField, IntegerField
from db_manager.db_conf import db
from models.team.team import Team

class TeamRegularSeasonResults(Model):
    
    id_team_regular_season_results = AutoField(primary_key=True)
    id_team = ForeignKeyField(Team, to_field="id_team")
    game = IntegerField(null=True)
    date_game = CharField()
    game_start_time = CharField()
    network = CharField(null = True)
    box_score_text = CharField()
    game_location = CharField(null=True)
    opp_name = CharField()
    game_result = CharField()
    overtimes = CharField(null=True)
    pts =  CharField()
    opp_pts = CharField()
    wins = CharField()
    losses = CharField()
    game_streak = CharField()
    attendance = CharField()
    game_duration = CharField()
    game_remarks = CharField(null=True)
    year = IntegerField(null=True)
    
    class Meta:
        database = db
        schema = 'teams'
        table_name = 'team_regular_season_results'